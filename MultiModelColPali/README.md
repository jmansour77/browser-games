# DocVision — Multimodal Vision-First RAG Chatbot

**Ask questions about technical documents. Get answers grounded in both text *and* visuals.**

Built with **ColPali** (Vision-First retrieval) + **LanceDB** (multi-vector storage) + **Claude** (generation).

---

## Why Vision-First?

Traditional RAG systems extract text from PDFs and embed it. This loses:
- Diagrams and illustrations
- Table layouts
- Screenshots with UI elements
- Spatial relationships between content

**ColPali** treats each PDF page as an image and creates patch-level embeddings — no text extraction needed. Claude then *sees* the actual pages to answer your question.

---

## Architecture

```
PDF → [PyMuPDF] → Page Images
                        ↓
              [ColPali PaliGemma]
                        ↓
         Multi-vector patch embeddings
         (N_patches × 128 per page)
                        ↓
                  [LanceDB]
                        ↓
Query → [ColPali] → Query embedding
                        ↓
              MaxSim scoring (ColBERT-style)
                        ↓
              Top-K most relevant pages
                        ↓
           [Claude claude-sonnet-4-6 Vision]
                        ↓
                   Grounded Answer
```

---

## Setup

### Prerequisites
- Python 3.10 or 3.11
- 8–16 GB RAM (CPU) or 6–8 GB VRAM (GPU)
- Anthropic API key → https://console.anthropic.com

### Step 1 — Create virtual environment

```powershell
python -m venv venv
.\venv\Scripts\activate
```

### Step 2 — Install PyTorch

**GPU (CUDA 12.1):**
```powershell
pip install torch==2.5.1 torchvision --index-url https://download.pytorch.org/whl/cu121
```

**CPU only:**
```powershell
pip install torch==2.5.1 torchvision --index-url https://download.pytorch.org/whl/cpu
```

### Step 3 — Install remaining dependencies

```powershell
pip install -r requirements.txt
```

### Step 4 — Configure API key

```powershell
copy .env.example .env
# Open .env and set ANTHROPIC_API_KEY=sk-ant-...
```

### Step 5 — Ingest your document (one-time)

```powershell
python ingest.py "documents/Designer User Manual En.pdf"
```

**Expected time:**
| Hardware | 86 pages |
|---|---|
| NVIDIA GPU (8GB+) | ~3–8 minutes |
| CPU (16GB RAM) | 2–8 hours |

The ingestion is **resumable** — re-running skips already-processed pages.

### Step 6 — Launch the chatbot

```powershell
streamlit run app.py
```

Browser opens at **http://localhost:8501**

---

## Adding More Documents

**Via the UI:** Use the "Upload PDF" button in the sidebar — ingestion runs automatically.

**Via CLI:**
```powershell
python ingest.py "documents/AnotherManual.pdf"
python ingest.py "documents/SystemDesign.pdf"
```

All documents are searched together in every query.

---

## File Structure

```
MultiModelColPali/
├── requirements.txt     # Python dependencies
├── .env.example         # Configuration template
├── .env                 # Your config (API key, etc.) — create from example
├── config.py            # All settings in one place
├── ingest.py            # PDF → ColPali embeddings → LanceDB
├── retrieval.py         # Query → MaxSim search → page images
├── generation.py        # Retrieved pages + Claude → answer
├── app.py               # Streamlit chatbot UI
├── documents/           # Put your PDFs here
│   └── Designer User Manual En.pdf
└── lancedb_store/       # Vector DB (auto-created)
```

---

## Verification Commands

```powershell
# Check all imports work
python -c "import colpali_engine, lancedb, anthropic, streamlit; print('All OK')"

# Check row count after ingestion
python -c "import lancedb, config; db=lancedb.connect(config.LANCEDB_PATH); t=db.open_table(config.LANCEDB_TABLE); print(f'{t.count_rows()} pages in DB')"

# Test retrieval standalone
python retrieval.py "how do I create a new project"

# Test generation standalone
python generation.py
```

---

## Configuration Options (`.env`)

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required — your Anthropic API key |
| `COLPALI_MODEL` | `vidore/colpali-v1.2` | ColPali model. Use `vidore/colqwen2-v1.0` for less RAM |
| `TOP_K_PAGES` | `3` | Pages retrieved per query |
| `MAX_TOKENS` | `2048` | Claude response length limit |
| `LANCEDB_PATH` | `./lancedb_store` | Vector DB storage location |
| `DOCUMENTS_DIR` | `./documents` | PDF documents folder |

---

## Troubleshooting

**Out of memory during ingestion:**
- Switch to `vidore/colqwen2-v1.0` (smaller model, ~8GB RAM vs ~12GB)
- Ingestion runs 1 page at a time on CPU; set `BATCH_SIZE_INGEST=1` in config

**Slow ingestion on CPU:**
- This is normal — ColPali runs a ~3B parameter vision model per page
- Ingestion is a one-time step; queries are fast afterwards
- The process is resumable (safe to Ctrl+C and re-run)

**"Table not found" error:**
- Run `python ingest.py "documents/Your File.pdf"` before starting the app

**Model download fails:**
- ColPali downloads from Hugging Face (~4–12 GB first time)
- Set `HF_HOME` env var to change cache location if disk space is limited
