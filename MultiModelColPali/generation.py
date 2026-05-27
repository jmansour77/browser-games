"""
generation.py — Retrieved page images + conversation history → Claude answer

Uses claude-sonnet-4-6 with vision to answer questions grounded in the
retrieved document pages. Maintains multi-turn conversation history.

Key design decisions:
  - Only the CURRENT turn's images are sent to Claude (images in older
    turns are replaced with text placeholders to control token cost)
  - Pages are interleaved with captions so Claude can correlate images
    with specific document/page references
  - System prompt instructs citation of page numbers
"""

import base64
import functools
import io
from typing import Optional

from PIL import Image

import config


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a helpful technical document assistant with vision capabilities.

You will be shown pages from one or more technical documents as images.
Your job is to answer the user's questions accurately and clearly based ONLY on what you can see in the provided pages.

Guidelines:
- Always cite the specific page number(s) when referencing information (e.g., "According to page 23...")
- If the answer spans multiple pages, reference all relevant pages
- If the information is not visible in the provided pages, say so clearly — do not guess
- For instructions or steps, preserve their order and completeness
- For diagrams, tables, or screenshots, describe what they show
- Keep answers concise but complete"""


# ── Client singleton ──────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def get_anthropic_client():
    """Return a cached Anthropic client instance."""
    import anthropic
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


# ── Image encoding ────────────────────────────────────────────────────────────

def image_to_base64(image: Image.Image, quality: int = config.JPEG_QUALITY) -> str:
    """
    Encode a PIL Image as a base64 JPEG string for the Anthropic API.
    """
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality, optimize=True)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def build_image_block(image: Image.Image) -> dict:
    """Return an Anthropic API image content block."""
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": image_to_base64(image),
        },
    }


# ── Message construction ──────────────────────────────────────────────────────

def build_user_message(query: str, retrieved_pages: list[dict]) -> list[dict]:
    """
    Build a multimodal user message content list.

    The format interleaves images with captions, then ends with the question.
    This helps Claude correlate each image with its document/page reference.

    Example structure:
        [text: "Here are 3 relevant pages:"]
        [image: page 5 JPEG]
        [text: "↑ Designer User Manual En — Page 5"]
        [image: page 12 JPEG]
        [text: "↑ Designer User Manual En — Page 12"]
        [text: "Question: ..."]

    Args:
        query:           The user's question.
        retrieved_pages: List of dicts from retrieval.retrieve_pages().

    Returns:
        Anthropic API content list (list of content blocks).
    """
    n = len(retrieved_pages)
    content = [
        {
            "type": "text",
            "text": (
                f"I'm showing you {n} relevant page{'s' if n != 1 else ''} "
                f"from the document{'s' if n != 1 else ''}:"
            ),
        }
    ]

    for page in retrieved_pages:
        # Add the page image
        content.append(build_image_block(page["image"]))
        # Add a caption so Claude knows which document/page this is
        content.append({
            "type": "text",
            "text": (
                f"↑ **{page['doc_name']}** — Page {page['page_num'] + 1}"
                f"  (relevance score: {page['score']:.3f})"
            ),
        })

    # End with the actual question
    content.append({
        "type": "text",
        "text": (
            f"\n---\n"
            f"**Question:** {query}\n\n"
            f"Please answer based on the pages shown above. "
            f"Cite specific page numbers when referencing information."
        ),
    })

    return content


def trim_history_images(history: list[dict]) -> list[dict]:
    """
    Replace image blocks in all but the last user message with text placeholders.

    Keeps conversation context (text) while dropping the large image blobs
    from older turns to control token cost and context window size.

    Args:
        history: Full Anthropic API messages list.

    Returns:
        New list with images removed from non-latest user messages.
    """
    if not history:
        return history

    trimmed = []
    # Find the index of the last user message
    last_user_idx = max(
        (i for i, msg in enumerate(history) if msg["role"] == "user"),
        default=-1
    )

    for i, msg in enumerate(history):
        if msg["role"] == "user" and i < last_user_idx:
            # Replace image blocks with a placeholder in older turns
            new_content = []
            image_count = 0
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "image":
                    image_count += 1
                else:
                    new_content.append(block)
            if image_count > 0:
                new_content.insert(0, {
                    "type": "text",
                    "text": f"[{image_count} document page image(s) — removed to save context]",
                })
            trimmed.append({"role": "user", "content": new_content})
        else:
            trimmed.append(msg)

    return trimmed


# ── Main generation function ──────────────────────────────────────────────────

def generate_answer(
    query: str,
    retrieved_pages: list[dict],
    conversation_history: list[dict],
    client=None,
) -> tuple[str, list[dict]]:
    """
    Generate a grounded answer using Claude with the retrieved page images.

    Args:
        query:                The user's question.
        retrieved_pages:      Top-K pages from retrieval (with images).
        conversation_history: Existing Anthropic API messages list (for multi-turn).
        client:               anthropic.Anthropic instance (or None to use cached).

    Returns:
        (answer_text, updated_history)
        - answer_text:      Claude's response string.
        - updated_history:  History with the new user + assistant turn appended.
    """
    if client is None:
        client = get_anthropic_client()

    # Build the multimodal user message for this turn
    user_content = build_user_message(query, retrieved_pages)

    # Start from the existing history, trim old images to save tokens
    history = trim_history_images(list(conversation_history))

    # Append the new user message
    history.append({"role": "user", "content": user_content})

    # Call Claude
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=config.MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=history,
    )

    answer_text = response.content[0].text

    # Append assistant response to history
    history.append({"role": "assistant", "content": answer_text})

    return answer_text, history


# ── Standalone test ───────────────────────────────────────────────────────────

def main():
    """Quick end-to-end test: retrieve pages and generate an answer."""
    from ingest import load_colpali_model
    from retrieval import retrieve_pages

    query = "What is this document about? Give me a brief overview."
    print(f"[generation] Test query: '{query}'\n")

    print("[generation] Loading ColPali model...")
    model, processor = load_colpali_model()

    print("[generation] Retrieving pages...")
    pages = retrieve_pages(query, model, processor, top_k=2)
    for p in pages:
        print(f"  → {p['doc_name']} page {p['page_num'] + 1} (score: {p['score']:.4f})")

    print("\n[generation] Calling Claude...")
    client = get_anthropic_client()
    answer, _ = generate_answer(query, pages, [], client)

    print("\n─── Claude's Answer ───────────────────────────────────────")
    print(answer)
    print("───────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
