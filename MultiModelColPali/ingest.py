"""
ingest.py — PDF → page images → ColPali multi-vector embeddings → LanceDB

Usage (CLI):
    python ingest.py "documents/Designer User Manual En.pdf"
    python ingest.py "documents/AnotherDoc.pdf"   # add more docs anytime

The ingestion is idempotent: already-stored pages are skipped automatically,
so it's safe to re-run or resume after interruption.
"""

import argparse
import functools
import io
import sys
from pathlib import Path
from typing import Generator

import numpy as np
import pyarrow as pa
import torch
from PIL import Image
from tqdm import tqdm

import config

# ── LanceDB schema ────────────────────────────────────────────────────────────
# Each row = one PDF page.
# embeddings_flat: ColPali (N_patches, 128) tensor flattened to 1-D list.
# n_patches:       number of patches (needed to reshape at query time).
# image_bytes:     JPEG-compressed page image (for display in the UI).
PAGES_SCHEMA = pa.schema([
    pa.field("embeddings_flat", pa.list_(pa.float32())),
    pa.field("n_patches",       pa.int32()),
    pa.field("image_bytes",     pa.large_binary()),
    pa.field("doc_name",        pa.string()),
    pa.field("page_num",        pa.int32()),   # 0-indexed
    pa.field("doc_path",        pa.string()),
])


# ── Model loading ─────────────────────────────────────────────────────────────

def _get_model_classes():
    """
    Return the correct (ModelClass, ProcessorClass) for the configured model.

    colpali-v1.x  → ColPali      + ColPaliProcessor
    colqwen2-v*   → ColQwen2     + ColQwen2Processor
    """
    model_name = config.COLPALI_MODEL.lower()
    if "colqwen2" in model_name or "qwen2" in model_name:
        from colpali_engine.models import ColQwen2, ColQwen2Processor
        return ColQwen2, ColQwen2Processor
    else:
        from colpali_engine.models import ColPali, ColPaliProcessor
        return ColPali, ColPaliProcessor


@functools.lru_cache(maxsize=1)
def load_colpali_model():
    """
    Load the ColPali/ColQwen2 model and processor.
    Cached with lru_cache so repeated calls don't reload the model.

    Supports both:
      - vidore/colpali-v1.2    (PaliGemma 3B)
      - vidore/colqwen2-v1.0   (Qwen2-VL 2B, lighter — recommended for CPU)

    Returns:
        (model, processor) tuple, both ready for inference.
    """
    ModelClass, ProcessorClass = _get_model_classes()
    print(f"[ingest] Loading '{config.COLPALI_MODEL}' ({ModelClass.__name__}) on {config.DEVICE}...")

    # bfloat16 on GPU halves VRAM; float32 required on CPU
    dtype = torch.bfloat16 if config.DEVICE == "cuda" else torch.float32

    model = ModelClass.from_pretrained(
        config.COLPALI_MODEL,
        torch_dtype=dtype,
        device_map=config.DEVICE,
    ).eval()

    processor = ProcessorClass.from_pretrained(config.COLPALI_MODEL)

    print(f"[ingest] Model loaded. Parameters: {sum(p.numel() for p in model.parameters()):,}")
    return model, processor


# ── PDF rendering ─────────────────────────────────────────────────────────────

def pdf_to_images(pdf_path: str, dpi: int = config.IMAGE_DPI) -> list[Image.Image]:
    """
    Render every page of a PDF as an RGB PIL Image.

    Uses PyMuPDF (fitz) — no Poppler required on Windows.

    Args:
        pdf_path: Path to the PDF file.
        dpi:      Rendering resolution. 150 dpi is a good balance for ColPali.

    Returns:
        List of PIL Images, one per page.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    matrix = fitz.Matrix(dpi / 72, dpi / 72)   # scale from 72-dpi PDF units
    images = []

    for page in doc:
        pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)

    doc.close()
    print(f"[ingest] Rendered {len(images)} pages from '{Path(pdf_path).name}' at {dpi} dpi")
    return images


# ── ColPali embedding ─────────────────────────────────────────────────────────

def embed_pages_batched(
    images: list[Image.Image],
    model,
    processor,
    batch_size: int = config.BATCH_SIZE_INGEST,
) -> Generator[np.ndarray, None, None]:
    """
    Yield per-page embeddings as numpy arrays, processing in batches.

    Each yielded array has shape (N_patches, 128), dtype float32.
    The arrays are L2-normalised by ColPali's forward pass.

    Args:
        images:     List of PIL Images (one per page).
        model:      Loaded ColPali model.
        processor:  Loaded ColPaliProcessor.
        batch_size: Pages per forward pass (4 on GPU, 1 on CPU).

    Yields:
        np.ndarray of shape (N_patches, 128) for each page.
    """
    for i in range(0, len(images), batch_size):
        batch_images = images[i : i + batch_size]

        # process_images returns a BatchFeature (dict of tensors)
        batch_input = processor.process_images(batch_images).to(model.device)

        with torch.no_grad():
            # embeddings shape: (batch_size, N_patches, 128)
            embeddings = model(**batch_input)

        # Convert to float32 numpy for storage (bfloat16 not supported by numpy)
        embeddings_np = embeddings.float().cpu().numpy()

        for page_emb in embeddings_np:
            yield page_emb   # shape: (N_patches, 128)


# ── LanceDB helpers ───────────────────────────────────────────────────────────

def get_or_create_table(db):
    """
    Open the 'pages' table if it exists, or create it with the correct schema.

    Args:
        db: lancedb.DBConnection

    Returns:
        lancedb.Table
    """
    import lancedb

    if config.LANCEDB_TABLE in db.table_names():
        return db.open_table(config.LANCEDB_TABLE)

    print(f"[ingest] Creating new LanceDB table '{config.LANCEDB_TABLE}'")
    # Create with an empty initial batch to register the schema
    empty = pa.RecordBatch.from_pydict(
        {field.name: [] for field in PAGES_SCHEMA},
        schema=PAGES_SCHEMA,
    )
    return db.create_table(config.LANCEDB_TABLE, data=pa.Table.from_batches([empty]))


def page_already_ingested(table, doc_name: str, page_num: int) -> bool:
    """
    Return True if this (doc_name, page_num) pair is already in the table.
    Used to make ingestion idempotent.
    """
    try:
        results = (
            table.search()
            .where(f"doc_name = '{doc_name}' AND page_num = {page_num}", prefilter=True)
            .limit(1)
            .to_list()
        )
        return len(results) > 0
    except Exception:
        return False


def image_to_jpeg_bytes(image: Image.Image, quality: int = config.JPEG_QUALITY) -> bytes:
    """Compress a PIL Image to JPEG bytes for compact storage."""
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


# ── Main ingestion orchestrator ───────────────────────────────────────────────

def ingest_pdf(pdf_path: str, db_path: str = config.LANCEDB_PATH) -> dict:
    """
    Full ingestion pipeline for one PDF file.

    Steps:
        1. Render PDF pages to images (PyMuPDF)
        2. Load ColPali model
        3. Embed pages in batches
        4. Store embeddings + images + metadata in LanceDB

    Already-ingested pages are skipped (idempotent).

    Args:
        pdf_path: Path to the PDF file.
        db_path:  LanceDB storage directory.

    Returns:
        dict with keys: doc_name, total_pages, ingested, skipped
    """
    import lancedb

    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc_name = pdf_path.stem   # filename without extension
    print(f"\n[ingest] ═══ Ingesting: {pdf_path.name} ═══")

    # 1. Render pages
    images = pdf_to_images(str(pdf_path))
    total_pages = len(images)

    # 2. Open DB and table
    db = lancedb.connect(db_path)
    table = get_or_create_table(db)

    # 3. Check which pages still need embedding
    pages_to_embed = [
        (idx, img) for idx, img in enumerate(images)
        if not page_already_ingested(table, doc_name, idx)
    ]

    skipped = total_pages - len(pages_to_embed)
    if skipped > 0:
        print(f"[ingest] Skipping {skipped} already-ingested page(s)")
    if not pages_to_embed:
        print(f"[ingest] All {total_pages} pages already in DB — nothing to do.")
        return {"doc_name": doc_name, "total_pages": total_pages, "ingested": 0, "skipped": skipped}

    # 4. Load model
    model, processor = load_colpali_model()

    # 5. Embed and store page by page (with progress bar)
    page_indices = [p[0] for p in pages_to_embed]
    page_images  = [p[1] for p in pages_to_embed]

    ingested = 0
    emb_gen = embed_pages_batched(page_images, model, processor)

    with tqdm(total=len(pages_to_embed), desc=f"Embedding '{doc_name}'", unit="page") as pbar:
        for local_idx, page_emb in enumerate(emb_gen):
            page_num = page_indices[local_idx]
            orig_image = page_images[local_idx]

            # Compress page image to JPEG bytes
            jpeg_bytes = image_to_jpeg_bytes(orig_image)

            # Build the LanceDB record
            record = {
                "embeddings_flat": page_emb.flatten().astype(np.float32).tolist(),
                "n_patches":       int(page_emb.shape[0]),
                "image_bytes":     jpeg_bytes,
                "doc_name":        doc_name,
                "page_num":        page_num,
                "doc_path":        str(pdf_path),
            }

            table.add([record])
            ingested += 1
            pbar.update(1)
            pbar.set_postfix({"page": page_num + 1, "patches": page_emb.shape[0]})

    print(f"\n[ingest] ✓ Done — {ingested} pages ingested, {skipped} skipped.")
    print(f"[ingest] Total rows in DB: {table.count_rows()}")

    return {
        "doc_name":    doc_name,
        "total_pages": total_pages,
        "ingested":    ingested,
        "skipped":     skipped,
    }


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ingest PDF documents into the ColPali + LanceDB vector store."
    )
    parser.add_argument(
        "pdfs",
        nargs="+",
        metavar="PDF_PATH",
        help="Path(s) to PDF file(s) to ingest.",
    )
    parser.add_argument(
        "--db",
        default=config.LANCEDB_PATH,
        metavar="DB_PATH",
        help=f"LanceDB storage directory (default: {config.LANCEDB_PATH})",
    )
    args = parser.parse_args()

    results = []
    for pdf_path in args.pdfs:
        try:
            result = ingest_pdf(pdf_path, db_path=args.db)
            results.append(result)
        except FileNotFoundError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Failed to ingest '{pdf_path}': {e}", file=sys.stderr)
            raise

    print("\n[ingest] ═══ Summary ═══")
    for r in results:
        print(
            f"  {r['doc_name']}: "
            f"{r['ingested']} ingested, {r['skipped']} skipped "
            f"({r['total_pages']} total pages)"
        )


if __name__ == "__main__":
    main()
