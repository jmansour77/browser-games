"""
app.py — Streamlit chatbot UI for the Multimodal Vision-First RAG system

Run with:
    streamlit run app.py
"""

import sys
import os
from pathlib import Path
import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────
st.set_page_config(
    page_title="DocVision — Multimodal RAG Chatbot",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dependency check BEFORE any other imports ─────────────────────
MISSING_PKGS = []
for pkg, install_name in [
    ("colpali_engine", "colpali-engine"),
    ("lancedb",        "lancedb"),
    ("anthropic",      "anthropic"),
    ("fitz",           "pymupdf"),
    ("torch",          "torch"),
]:
    try:
        __import__(pkg)
    except ImportError:
        MISSING_PKGS.append(install_name)

if MISSING_PKGS:
    st.error("### ⚠️ Missing Python packages")
    st.markdown(
        "The following packages are not installed. "
        "Run the commands below in your terminal, then refresh this page."
    )

    st.markdown("**Step 1 — Install PyTorch** (choose one):")
    st.code(
        "# GPU (CUDA 12.1):\n"
        "pip install torch==2.5.1 torchvision --index-url https://download.pytorch.org/whl/cu121\n\n"
        "# CPU only:\n"
        "pip install torch==2.5.1 torchvision --index-url https://download.pytorch.org/whl/cpu",
        language="bash",
    )

    st.markdown("**Step 2 — Install all remaining dependencies:**")
    st.code("pip install -r requirements.txt", language="bash")

    st.markdown("**Missing packages detected:**")
    for p in MISSING_PKGS:
        st.markdown(f"- `{p}`")

    st.info(
        "💡 **Tip:** Make sure you activated your virtual environment first:\n"
        "```\n.\\venv\\Scripts\\activate\n```"
    )
    st.stop()

# ── Now safe to import everything ────────────────────────────────
import config

# ── .env / API key check ──────────────────────────────────────────
def _check_env() -> list[str]:
    """Return list of missing configuration items."""
    issues = []
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        issues.append("no_env_file")
    if not config.ANTHROPIC_API_KEY:
        issues.append("no_api_key")
    return issues

env_issues = _check_env()
if env_issues:
    st.error("### ⚙️ Setup Required")

    if "no_env_file" in env_issues:
        st.markdown("**1. Create your `.env` file:**")
        st.code(
            "copy .env.example .env",
            language="bash",
        )

    st.markdown("**2. Open `.env` and set your Anthropic API key:**")
    env_path = Path(__file__).parent / ".env"
    st.code(
        f"# File: {env_path}\nANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE",
        language="bash",
    )
    st.markdown(
        "Get your key at [console.anthropic.com](https://console.anthropic.com) → API Keys"
    )

    st.markdown("**3. Save the file and refresh this page.**")

    with st.expander("Still seeing this after setting the key?"):
        st.markdown(
            "- Make sure `.env` is in the same folder as `app.py`\n"
            "- Make sure there are no spaces around the `=` sign\n"
            "- Restart Streamlit: stop with `Ctrl+C`, then `streamlit run app.py` again"
        )
    st.stop()

# ── Custom CSS ────────────────────────────────────────────────────
st.markdown("""
<style>
.source-caption { font-size: 0.78rem; color: #6b7280; text-align: center; margin-top: 4px; }
.score-badge { background: #dbeafe; color: #1d4ed8; border-radius: 4px; padding: 1px 6px;
               font-size: 0.72rem; font-weight: 600; }
.main .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────
def _init():
    defaults = {
        "messages":          [],
        "api_history":       [],
        "colpali_model":     None,
        "colpali_processor": None,
        "anthropic_client":  None,
        "top_k":             config.TOP_K_PAGES,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()


# ── Model loading (cached once per Streamlit server process) ──────
@st.cache_resource(show_spinner=False)
def load_models():
    from ingest import load_colpali_model
    from generation import get_anthropic_client
    model, processor = load_colpali_model()
    client = get_anthropic_client()
    return model, processor, client


# ── LanceDB helpers ───────────────────────────────────────────────
def get_ingested_documents() -> list[dict]:
    try:
        import lancedb
        db = lancedb.connect(config.LANCEDB_PATH)
        if config.LANCEDB_TABLE not in db.table_names():
            return []
        table = db.open_table(config.LANCEDB_TABLE)
        rows = table.search().select(["doc_name"]).limit(None).to_list()
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["doc_name"]] = counts.get(row["doc_name"], 0) + 1
        return [{"doc_name": k, "page_count": v} for k, v in sorted(counts.items())]
    except Exception:
        return []


def db_is_empty() -> bool:
    try:
        import lancedb
        db = lancedb.connect(config.LANCEDB_PATH)
        if config.LANCEDB_TABLE not in db.table_names():
            return True
        return db.open_table(config.LANCEDB_TABLE).count_rows() == 0
    except Exception:
        return True


# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.title("📄 DocVision")
    st.caption("Vision-First RAG · ColPali + LanceDB + Claude")
    st.divider()

    # Upload & Ingest
    st.subheader("📥 Add Document")
    uploaded_file = st.file_uploader(
        "Upload a PDF", type=["pdf"], label_visibility="collapsed"
    )

    if uploaded_file is not None:
        docs_dir = Path(config.DOCUMENTS_DIR)
        docs_dir.mkdir(parents=True, exist_ok=True)
        save_path = docs_dir / uploaded_file.name

        if not save_path.exists():
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"Saved **{uploaded_file.name}**")
        else:
            st.info(f"**{uploaded_file.name}** already saved.")

        if st.button("🔄 Ingest Document", type="primary", use_container_width=True):
            from ingest import ingest_pdf
            try:
                with st.spinner(f"Ingesting pages… (may take several minutes on CPU)"):
                    result = ingest_pdf(str(save_path))
                st.success(
                    f"**{result['doc_name']}**: "
                    f"{result['ingested']} pages ingested, "
                    f"{result['skipped']} skipped."
                )
                st.rerun()
            except Exception as e:
                st.error(f"Ingestion failed: {e}")

    st.divider()

    # Documents in DB
    st.subheader("📚 Knowledge Base")
    docs = get_ingested_documents()
    if docs:
        for doc in docs:
            st.markdown(
                f"🗂️ **{doc['doc_name']}**  "
                f"<span style='color:#6b7280'>({doc['page_count']} pages)</span>",
                unsafe_allow_html=True,
            )
    else:
        st.info(
            "No documents yet.\n\n"
            "Upload a PDF above, or run in terminal:\n"
            "```\npython ingest.py \"documents/Your File.pdf\"\n```"
        )

    st.divider()

    # Settings
    st.subheader("⚙️ Settings")
    st.session_state.top_k = st.slider(
        "Pages retrieved per query", 1, 5, st.session_state.top_k
    )
    st.caption(f"ColPali: `{config.COLPALI_MODEL}`")
    st.caption(f"Device: `{config.DEVICE}`")
    st.caption(f"Claude: `{config.CLAUDE_MODEL}`")
    st.divider()

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.api_history = []
        st.rerun()


# ── Main area ─────────────────────────────────────────────────────
st.title("💬 Document Chatbot")

# Load ColPali + Anthropic client (heavy — runs once, cached)
with st.spinner("Loading ColPali vision model… (first load takes ~1 min)"):
    try:
        model, processor, anthropic_client = load_models()
        st.session_state.colpali_model     = model
        st.session_state.colpali_processor = processor
        st.session_state.anthropic_client  = anthropic_client
    except Exception as e:
        st.error(f"**Failed to load model:** {e}")
        st.markdown(
            "**Common fixes:**\n"
            "- Make sure PyTorch is installed: `pip install torch==2.5.1`\n"
            "- Make sure colpali-engine is installed: `pip install colpali-engine`\n"
            "- Check your internet connection (model downloads from Hugging Face ~4–12 GB first time)\n"
            "- If out of memory: switch model to `vidore/colqwen2-v1.0` in `.env`"
        )
        st.stop()

# Prompt to ingest if DB is empty
if db_is_empty():
    st.info(
        "👋 **Welcome!** No documents have been ingested yet.\n\n"
        "**Get started in 2 steps:**\n\n"
        "**Option A — Terminal** (recommended for large files):\n"
        "```\npython ingest.py \"documents/Designer User Manual En.pdf\"\n```\n\n"
        "**Option B — Sidebar:** Use the 'Upload PDF' button above ↖\n\n"
        "*Ingestion is a one-time step. Queries are fast once it's done.*"
    )

# Render chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("retrieved_pages"):
            pages = msg["retrieved_pages"]
            with st.expander(f"📑 Source pages ({len(pages)})", expanded=False):
                cols = st.columns(len(pages))
                for i, page in enumerate(pages):
                    with cols[i]:
                        st.image(page["image"], use_container_width=True,
                                 caption=f"{page['doc_name']} — p.{page['page_num']+1}")
                        st.markdown(
                            f"<div class='source-caption'>"
                            f"<span class='score-badge'>score {page['score']:.3f}</span>"
                            f"</div>", unsafe_allow_html=True,
                        )

# Chat input
if prompt := st.chat_input(
    "Ask anything about your documents…",
    disabled=db_is_empty(),
):
    # Show user bubble
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Retrieve
        with st.spinner("🔍 Searching pages…"):
            try:
                from retrieval import retrieve_pages
                retrieved = retrieve_pages(
                    query=prompt,
                    model=st.session_state.colpali_model,
                    processor=st.session_state.colpali_processor,
                    top_k=st.session_state.top_k,
                )
            except Exception as e:
                st.error(f"Retrieval failed: {e}")
                st.stop()

        # Generate
        with st.spinner("🤖 Generating answer…"):
            try:
                from generation import generate_answer
                answer, updated_history = generate_answer(
                    query=prompt,
                    retrieved_pages=retrieved,
                    conversation_history=st.session_state.api_history,
                    client=st.session_state.anthropic_client,
                )
            except Exception as e:
                st.error(f"Generation failed: {e}")
                st.stop()

        st.session_state.api_history = updated_history

        # Display answer
        st.markdown(answer)

        # Source pages expander
        if retrieved:
            with st.expander(f"📑 Source pages ({len(retrieved)})", expanded=False):
                cols = st.columns(len(retrieved))
                for i, page in enumerate(retrieved):
                    with cols[i]:
                        st.image(page["image"], use_container_width=True,
                                 caption=f"{page['doc_name']} — p.{page['page_num']+1}")
                        st.markdown(
                            f"<div class='source-caption'>"
                            f"<span class='score-badge'>score {page['score']:.3f}</span>"
                            f"</div>", unsafe_allow_html=True,
                        )

    # Persist to display history
    st.session_state.messages.append({
        "role":            "assistant",
        "content":         answer,
        "retrieved_pages": retrieved,
    })
