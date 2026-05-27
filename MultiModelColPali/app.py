"""
app.py — Streamlit chatbot UI for the Multimodal Vision-First RAG system

Run with:
    streamlit run app.py

Layout:
    ┌──────────────────┬────────────────────────────────────┐
    │  SIDEBAR         │  MAIN CHAT                         │
    │                  │                                    │
    │ [Upload PDF]     │  Chat messages with retrieved      │
    │ [Ingest status]  │  source page thumbnails            │
    │                  │                                    │
    │ Documents in DB  │  [Chat input at bottom]            │
    │ Top-K slider     │                                    │
    │ [Clear Chat]     │                                    │
    └──────────────────┴────────────────────────────────────┘
"""

import io
import os
import tempfile
from pathlib import Path

import streamlit as st

import config

# ── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DocVision — Multimodal RAG Chatbot",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Source page thumbnails */
.source-caption {
    font-size: 0.78rem;
    color: #6b7280;
    text-align: center;
    margin-top: 4px;
}
.score-badge {
    background: #dbeafe;
    color: #1d4ed8;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 0.72rem;
    font-weight: 600;
}
/* Chat area top padding */
.main .block-container {
    padding-top: 1.5rem;
}
</style>
""", unsafe_allow_html=True)


# ── Session state initialisation ──────────────────────────────────────────────

def init_session_state():
    """Initialise all session state keys on first run."""
    if "messages" not in st.session_state:
        st.session_state.messages = []        # display history
    if "api_history" not in st.session_state:
        st.session_state.api_history = []     # Anthropic API messages history
    if "colpali_model" not in st.session_state:
        st.session_state.colpali_model = None
    if "colpali_processor" not in st.session_state:
        st.session_state.colpali_processor = None
    if "anthropic_client" not in st.session_state:
        st.session_state.anthropic_client = None
    if "top_k" not in st.session_state:
        st.session_state.top_k = config.TOP_K_PAGES


init_session_state()


# ── Model loading (cached in session state) ───────────────────────────────────

@st.cache_resource(show_spinner=False)
def load_models():
    """Load ColPali model and Anthropic client once per Streamlit session."""
    from ingest import load_colpali_model
    from generation import get_anthropic_client

    model, processor = load_colpali_model()
    client = get_anthropic_client()
    return model, processor, client


# ── LanceDB helpers ───────────────────────────────────────────────────────────

def get_ingested_documents() -> list[dict]:
    """
    Return a list of dicts describing documents currently in LanceDB.
    Each dict: {doc_name, page_count}
    """
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


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📄 DocVision")
    st.caption("Multimodal RAG — ColPali + LanceDB + Claude")
    st.divider()

    # ── Upload and ingest section ─────────────────────────────────────────────
    st.subheader("📥 Add Document")

    uploaded_file = st.file_uploader(
        "Upload a PDF",
        type=["pdf"],
        help="Upload a new PDF to add to the knowledge base.",
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        # Save to documents directory
        docs_dir = Path(config.DOCUMENTS_DIR)
        docs_dir.mkdir(parents=True, exist_ok=True)
        save_path = docs_dir / uploaded_file.name

        if save_path.exists():
            st.warning(f"**{uploaded_file.name}** already exists. Re-ingesting any missing pages.")
        else:
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"Saved **{uploaded_file.name}**")

        if st.button("🔄 Ingest Document", type="primary", use_container_width=True):
            from ingest import ingest_pdf, pdf_to_images

            # Count pages for progress bar
            try:
                images = pdf_to_images(str(save_path))
                total_pages = len(images)
            except Exception as e:
                st.error(f"Could not read PDF: {e}")
                st.stop()

            progress_bar = st.progress(0, text="Starting ingestion...")
            status_text  = st.empty()

            # Monkey-patch tqdm to update the Streamlit progress bar
            # We run ingestion with a custom callback approach via a wrapper
            ingested_so_far = [0]

            def _progress_callback(page_idx, total):
                pct = int((page_idx + 1) / total * 100)
                progress_bar.progress(pct, text=f"Embedding page {page_idx + 1} / {total}...")
                ingested_so_far[0] = page_idx + 1

            # Ingest (this is the heavy step)
            try:
                with st.spinner(f"Ingesting {total_pages} pages… (may take several minutes on CPU)"):
                    result = ingest_pdf(str(save_path))
                progress_bar.progress(100, text="✅ Ingestion complete!")
                status_text.success(
                    f"**{result['doc_name']}**: "
                    f"{result['ingested']} pages ingested, "
                    f"{result['skipped']} skipped."
                )
            except Exception as e:
                progress_bar.empty()
                st.error(f"Ingestion failed: {e}")

    st.divider()

    # ── Documents in DB ───────────────────────────────────────────────────────
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
        st.info("No documents ingested yet.\nUpload a PDF above or run:\n```\npython ingest.py <path>\n```")

    st.divider()

    # ── Settings ──────────────────────────────────────────────────────────────
    st.subheader("⚙️ Settings")
    st.session_state.top_k = st.slider(
        "Retrieved pages per query",
        min_value=1, max_value=5,
        value=st.session_state.top_k,
        help="How many document pages to retrieve and show to Claude.",
    )

    st.caption(f"Model: `{config.COLPALI_MODEL}`")
    st.caption(f"Device: `{config.DEVICE}`")
    st.caption(f"Claude: `{config.CLAUDE_MODEL}`")

    st.divider()

    # ── Clear chat ────────────────────────────────────────────────────────────
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.api_history = []
        st.rerun()


# ── Main chat area ────────────────────────────────────────────────────────────

st.title("💬 Document Chatbot")

# Load models (cached — runs once)
with st.spinner("Loading ColPali vision model… (first load takes a minute)"):
    try:
        model, processor, anthropic_client = load_models()
        st.session_state.colpali_model     = model
        st.session_state.colpali_processor = processor
        st.session_state.anthropic_client  = anthropic_client
    except Exception as e:
        st.error(f"Failed to load models: {e}")
        st.stop()

# ── DB empty warning ──────────────────────────────────────────────────────────
if db_is_empty():
    st.info(
        "👋 **Welcome!** No documents have been ingested yet.\n\n"
        "**To get started:**\n"
        "1. Upload a PDF in the sidebar, or\n"
        "2. Run `python ingest.py \"documents/Designer User Manual En.pdf\"` in your terminal\n\n"
        "Then come back here to start chatting!"
    )

# ── Display chat history ──────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Show retrieved source pages for assistant messages
        if msg["role"] == "assistant" and msg.get("retrieved_pages"):
            pages = msg["retrieved_pages"]
            with st.expander(f"📑 Source pages used ({len(pages)})", expanded=False):
                cols = st.columns(len(pages))
                for i, page in enumerate(pages):
                    with cols[i]:
                        st.image(
                            page["image"],
                            use_container_width=True,
                            caption=(
                                f"{page['doc_name']}\n"
                                f"Page {page['page_num'] + 1}"
                            ),
                        )
                        st.markdown(
                            f"<div class='source-caption'>"
                            f"<span class='score-badge'>score {page['score']:.3f}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

# ── Chat input ────────────────────────────────────────────────────────────────
if prompt := st.chat_input(
    "Ask anything about your documents…",
    disabled=db_is_empty(),
):
    # 1. Show user message immediately
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Retrieve relevant pages
    with st.chat_message("assistant"):
        with st.spinner("🔍 Searching document pages…"):
            try:
                from retrieval import retrieve_pages
                retrieved = retrieve_pages(
                    query=prompt,
                    model=st.session_state.colpali_model,
                    processor=st.session_state.colpali_processor,
                    top_k=st.session_state.top_k,
                )
            except RuntimeError as e:
                st.error(str(e))
                st.stop()

        # 3. Generate answer with Claude
        with st.spinner("🤖 Generating answer…"):
            from generation import generate_answer
            answer, updated_history = generate_answer(
                query=prompt,
                retrieved_pages=retrieved,
                conversation_history=st.session_state.api_history,
                client=st.session_state.anthropic_client,
            )

        st.session_state.api_history = updated_history

        # 4. Display answer
        st.markdown(answer)

        # 5. Show source pages in expander
        if retrieved:
            with st.expander(f"📑 Source pages used ({len(retrieved)})", expanded=False):
                cols = st.columns(len(retrieved))
                for i, page in enumerate(retrieved):
                    with cols[i]:
                        st.image(
                            page["image"],
                            use_container_width=True,
                            caption=(
                                f"{page['doc_name']}\n"
                                f"Page {page['page_num'] + 1}"
                            ),
                        )
                        st.markdown(
                            f"<div class='source-caption'>"
                            f"<span class='score-badge'>score {page['score']:.3f}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

    # 6. Persist assistant message to display history
    st.session_state.messages.append({
        "role":            "assistant",
        "content":         answer,
        "retrieved_pages": retrieved,
    })
