"""
retrieval.py — Query → ColPali embedding → MaxSim scan → top-K page images

The retrieval uses ColBERT-style late interaction (MaxSim):
  - Each query token finds its best-matching page patch (max similarity)
  - Scores are summed across all query tokens
  - Pages are ranked by this aggregated score

For corpora up to ~1000 pages, a full scan is fast enough (< 50ms in numpy).
No ANN index is needed at this scale.

Standalone test:
    python retrieval.py "how do I create a report"
"""

import argparse
import io
from typing import Optional

import numpy as np
from PIL import Image

import config


# ── MaxSim scoring (ColBERT-style late interaction) ───────────────────────────

def maxsim_score(query_emb: np.ndarray, page_emb: np.ndarray) -> float:
    """
    Compute the MaxSim score between a query and a document page.

    Both embeddings are L2-normalized by ColPali's forward pass, so the
    dot product equals cosine similarity.

    Algorithm:
        S[i,j] = similarity between query token i and page patch j
        score  = Σ_i  max_j  S[i,j]

    Args:
        query_emb: (N_q, 128) — query token embeddings
        page_emb:  (N_p, 128) — page patch embeddings

    Returns:
        Scalar MaxSim score (higher = more relevant).
    """
    # (N_q, N_p) similarity matrix
    sim_matrix = query_emb @ page_emb.T
    # For each query token: max similarity over all page patches
    # Then sum across query tokens
    return float(sim_matrix.max(axis=1).sum())


# ── Query embedding ───────────────────────────────────────────────────────────

def embed_query(query_text: str, model, processor) -> np.ndarray:
    """
    Embed a text query using ColPali's query encoder.

    Args:
        query_text: The user's question string.
        model:      Loaded ColPali model.
        processor:  Loaded ColPaliProcessor.

    Returns:
        np.ndarray of shape (N_q, 128) — query token embeddings, float32.
    """
    import torch

    batch = processor.process_queries([query_text]).to(model.device)

    with torch.no_grad():
        # Output shape: (1, N_q, 128)
        q_emb = model(**batch)

    # Squeeze batch dim, convert to float32 numpy
    return q_emb[0].float().cpu().numpy()   # (N_q, 128)


# ── Main retrieval function ───────────────────────────────────────────────────

def retrieve_pages(
    query: str,
    model,
    processor,
    db_path: str = config.LANCEDB_PATH,
    top_k: int = config.TOP_K_PAGES,
) -> list[dict]:
    """
    Retrieve the top-K most relevant pages for a query.

    Steps:
        1. Embed the query text with ColPali
        2. Load all rows from LanceDB (full scan)
        3. Compute MaxSim score for each page
        4. Sort descending, return top_k results

    Args:
        query:      The user's question.
        model:      Loaded ColPali model.
        processor:  Loaded ColPaliProcessor.
        db_path:    LanceDB storage directory.
        top_k:      Number of pages to return.

    Returns:
        List of dicts, each containing:
            - score    (float)    — MaxSim relevance score
            - doc_name (str)      — document name
            - page_num (int)      — 0-indexed page number
            - image    (PIL.Image)— decoded page image
        Sorted by score descending (most relevant first).
    """
    import lancedb

    # 1. Embed the query
    query_emb = embed_query(query, model, processor)   # (N_q, 128)

    # 2. Open DB and load all rows
    db = lancedb.connect(db_path)
    if config.LANCEDB_TABLE not in db.table_names():
        raise RuntimeError(
            f"LanceDB table '{config.LANCEDB_TABLE}' not found. "
            "Run 'python ingest.py <pdf>' first."
        )

    table = db.open_table(config.LANCEDB_TABLE)
    rows = table.search().select([
        "embeddings_flat", "n_patches", "image_bytes", "doc_name", "page_num"
    ]).limit(None).to_list()

    if not rows:
        return []

    # 3. Score every page
    scored = []
    for row in rows:
        page_emb = np.array(row["embeddings_flat"], dtype=np.float32).reshape(
            row["n_patches"], config.EMBEDDING_DIM
        )
        score = maxsim_score(query_emb, page_emb)
        scored.append((score, row))

    # 4. Sort descending by score, take top_k
    scored.sort(key=lambda x: x[0], reverse=True)
    top_results = scored[:top_k]

    # 5. Decode images and build output dicts
    results = []
    for score, row in top_results:
        image = Image.open(io.BytesIO(bytes(row["image_bytes"])))
        results.append({
            "score":    score,
            "doc_name": row["doc_name"],
            "page_num": row["page_num"],   # 0-indexed; display as page_num+1
            "image":    image,
        })

    return results


# ── Batch retrieval for multiple queries ──────────────────────────────────────

def retrieve_pages_batch(
    queries: list[str],
    model,
    processor,
    db_path: str = config.LANCEDB_PATH,
    top_k: int = config.TOP_K_PAGES,
) -> list[list[dict]]:
    """
    Retrieve pages for multiple queries in one LanceDB scan pass.
    More efficient than calling retrieve_pages() repeatedly.

    Returns:
        List of result lists, one per query.
    """
    import lancedb

    # Embed all queries
    query_embs = [embed_query(q, model, processor) for q in queries]

    # Load all rows once
    db = lancedb.connect(db_path)
    if config.LANCEDB_TABLE not in db.table_names():
        raise RuntimeError("No data ingested yet. Run python ingest.py first.")

    table = db.open_table(config.LANCEDB_TABLE)
    rows = table.search().select([
        "embeddings_flat", "n_patches", "image_bytes", "doc_name", "page_num"
    ]).limit(None).to_list()

    if not rows:
        return [[] for _ in queries]

    # Pre-compute page embeddings (reshape once)
    page_embs = [
        np.array(row["embeddings_flat"], dtype=np.float32).reshape(
            row["n_patches"], config.EMBEDDING_DIM
        )
        for row in rows
    ]

    all_results = []
    for query_emb in query_embs:
        scored = [
            (maxsim_score(query_emb, page_emb), row)
            for page_emb, row in zip(page_embs, rows)
        ]
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, row in scored[:top_k]:
            image = Image.open(io.BytesIO(bytes(row["image_bytes"])))
            results.append({
                "score":    score,
                "doc_name": row["doc_name"],
                "page_num": row["page_num"],
                "image":    image,
            })
        all_results.append(results)

    return all_results


# ── Standalone test ───────────────────────────────────────────────────────────

def main():
    from ingest import load_colpali_model

    parser = argparse.ArgumentParser(description="Test ColPali retrieval.")
    parser.add_argument("query", help="Query string to retrieve pages for.")
    parser.add_argument("--top_k", type=int, default=config.TOP_K_PAGES)
    args = parser.parse_args()

    print(f"[retrieval] Loading model...")
    model, processor = load_colpali_model()

    print(f"[retrieval] Query: '{args.query}'")
    results = retrieve_pages(args.query, model, processor, top_k=args.top_k)

    print(f"\n[retrieval] Top {len(results)} results:")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r['doc_name']}] Page {r['page_num'] + 1}  —  score: {r['score']:.4f}")


if __name__ == "__main__":
    main()
