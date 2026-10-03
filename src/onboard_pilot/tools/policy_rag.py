"""Policy handbook RAG (retrieval-augmented generation) tool.

Implementation deferred to step 04. For step 02, returns empty results.
Full implementation uses ChromaDB with local embeddings (DEVIATIONS P14).
"""

from onboard_pilot.schemas import ToolResult


def query_policy(question: str, k: int = 4) -> ToolResult:
    """Query the policy handbook via RAG.
    
    Args:
        question: Natural language question about policy
        k: Number of results to return (default 4)
    
    Returns:
        ToolResult with list of chunks {section_id, text, score}
    """
    # Stub implementation for step 02; full implementation in step 04
    return ToolResult(
        tool="query_policy",
        ok=True,
        data={"chunks": [], "question": question, "note": "RAG index not initialized yet"},
    )


def build_rag_index() -> ToolResult:
    """Build RAG index from policy_handbook.md.
    
    Called by scripts/init_all.py during initialization.
    Deferred to step 04.
    
    Returns:
        ToolResult with ok=True when complete
    """
    # Stub implementation; full implementation in step 04
    return ToolResult(
        tool="build_rag_index",
        ok=True,
        data={"message": "RAG index initialization deferred to step 04"},
    )
