"""Policy handbook RAG tool.

The handbook is split on `##`/`###` headings that carry a section id (e.g. `§3.2`) and
embedded with Chroma's default local embedding function (DEVIATIONS P14) into the
cosine-space collection `policy`. Headings without a section id (e.g. "### HR Coordinator")
stay inside the preceding section's chunk.
"""
import logging
import re
from pathlib import Path

from onboard_pilot.schemas import ToolResult

logger = logging.getLogger(__name__)

COLLECTION_NAME = "policy"
HANDBOOK_PATH = Path(__file__).resolve().parents[3] / "config" / "policy_handbook.md"
_HEADING_RE = re.compile(r"^(#{2,3})\s+(§\s*\d+(?:\.\d+)?)\b\s*(.*)$")


def split_handbook(text: str) -> list[dict]:
    """Split handbook markdown into chunks of {section_id, title, text}.

    Headings with no body of their own (e.g. a `##` that only introduces `###` children)
    produce no chunk.
    """
    chunks: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            if current:
                chunks.append(current)
            section_id = match.group(2).replace(" ", "")
            current = {"section_id": section_id, "title": match.group(3).strip(), "lines": [line]}
        elif current is not None:
            current["lines"].append(line)
    if current:
        chunks.append(current)

    result = []
    for c in chunks:
        body = "\n".join(c["lines"][1:]).strip()
        if body:
            result.append(
                {
                    "section_id": c["section_id"],
                    "title": c["title"],
                    "text": "\n".join(c["lines"]).strip(),
                }
            )
    return result


def _get_client():
    import chromadb

    from config.settings import get_settings

    path = get_settings().chroma_dir
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))


def build_index(handbook_path: Path | None = None, client=None) -> int:
    """Drop and recreate the `policy` collection from the handbook. Returns chunk count."""
    client = client or _get_client()
    text = (handbook_path or HANDBOOK_PATH).read_text(encoding="utf-8")
    chunks = split_handbook(text)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:  # collection does not exist yet
        logger.debug("No existing '%s' collection to drop", COLLECTION_NAME)
    collection = client.create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    collection.add(
        ids=[c["section_id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[{"section_id": c["section_id"], "title": c["title"]} for c in chunks],
    )
    logger.info("Built policy index with %d chunks", len(chunks))
    return len(chunks)


def query_policy(question: str, k: int = 4, client=None) -> ToolResult:
    """Retrieve the handbook sections most relevant to a policy question.

    Returns chunks as {section_id, text, score}; score is cosine similarity in [0, 1].
    """
    try:
        client = client or _get_client()
        collection = client.get_collection(COLLECTION_NAME)
        res = collection.query(query_texts=[question], n_results=k)
    except Exception as e:  # missing index or embedding model failure are business failures
        return ToolResult(
            tool="query_policy",
            ok=False,
            error_code="RAG_UNAVAILABLE",
            error_message=f"Policy index unavailable: {e}",
        )
    chunks = [
        {
            "section_id": meta["section_id"],
            "text": doc,
            "score": max(0.0, min(1.0, 1.0 - dist)),
        }
        for doc, meta, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0]
        )
    ]
    return ToolResult(tool="query_policy", ok=True, data={"chunks": chunks})
