"""
config.py — Single source of truth for all settings.

All other modules import constants from here, never directly from os.environ.
Device detection and batch sizes are computed once at import time.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (same directory as this file)
_here = Path(__file__).parent
load_dotenv(_here / ".env")

# ── API Keys ──────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
# NOTE: We do NOT raise here so Streamlit can still load and show a setup guide.
# Modules that actually need the key (generation.py) will fail with a clear message.

# ── Model Settings ────────────────────────────────────────────────
COLPALI_MODEL: str = os.environ.get("COLPALI_MODEL", "vidore/colpali-v1.2")

# ── Paths ─────────────────────────────────────────────────────────
LANCEDB_PATH: str   = os.environ.get("LANCEDB_PATH",   str(_here / "lancedb_store"))
DOCUMENTS_DIR: str  = os.environ.get("DOCUMENTS_DIR",  str(_here / "documents"))

# Ensure documents folder exists
Path(DOCUMENTS_DIR).mkdir(parents=True, exist_ok=True)

# ── Retrieval ─────────────────────────────────────────────────────
TOP_K_PAGES: int = int(os.environ.get("TOP_K_PAGES", "3"))

# ── Generation ────────────────────────────────────────────────────
CLAUDE_MODEL: str  = "claude-sonnet-4-6"
MAX_TOKENS: int    = int(os.environ.get("MAX_TOKENS", "2048"))

# ── Ingestion ─────────────────────────────────────────────────────
IMAGE_DPI: int         = 150       # PDF rendering DPI — balances quality vs. file size
JPEG_QUALITY: int      = 85        # JPEG compression quality for stored page images
EMBEDDING_DIM: int     = 128       # ColPali patch embedding dimension (fixed by model)
LANCEDB_TABLE: str     = "pages"   # LanceDB table name

# ── Device Detection ──────────────────────────────────────────────
def _detect_device() -> str:
    """Return 'cuda' if a CUDA GPU is available, otherwise 'cpu'."""
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"

DEVICE: str = _detect_device()

# Batch size during ingestion:
#   GPU: process 4 pages at once for throughput
#   CPU: process 1 page at a time to avoid OOM (ColPali is ~12GB on CPU)
BATCH_SIZE_INGEST: int = 4 if DEVICE == "cuda" else 1

# ── Info on startup ───────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Device      : {DEVICE}")
    print(f"ColPali     : {COLPALI_MODEL}")
    print(f"LanceDB     : {LANCEDB_PATH}")
    print(f"Documents   : {DOCUMENTS_DIR}")
    print(f"Batch size  : {BATCH_SIZE_INGEST}")
    print(f"Claude model: {CLAUDE_MODEL}")
