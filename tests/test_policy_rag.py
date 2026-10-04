"""Policy RAG tests. Splitter tests are offline; the integration test needs the local model."""
import pytest

from onboard_pilot.tools.policy_rag import HANDBOOK_PATH, query_policy, split_handbook


def _chunks():
    return split_handbook(HANDBOOK_PATH.read_text(encoding="utf-8"))


def test_split_yields_section_ids():
    ids = {c["section_id"] for c in _chunks()}
    expected = {"§1", "§2", "§3.1", "§3.2", "§3.3", "§4.1", "§4.2", "§4.3", "§5.1", "§5.2",
                "§6.1", "§6.2", "§6.3", "§6.4", "§7.1", "§7.2", "§8.1", "§8.2", "§9.1",
                "§9.2", "§9.3"}
    assert expected <= ids


def test_split_ids_are_unique():
    ids = [c["section_id"] for c in _chunks()]
    assert len(ids) == len(set(ids))


def test_handbook_planted_contradiction_and_budgets():
    by_id = {c["section_id"]: c["text"] for c in _chunks()}
    assert "€500" in by_id["§6.4"]
    for amount in ("1,800", "2,200", "2,600", "3,000"):
        assert amount in by_id["§3.2"]
    assert "never receive aws_dev" in by_id["§4.3"]


def test_split_ignores_unnumbered_subheadings():
    by_id = {c["section_id"]: c["text"] for c in _chunks()}
    assert "### HR Coordinator" in by_id["§2"]


def test_query_policy_returns_error_result_when_index_missing(tmp_path):
    import chromadb

    result = query_policy("anything", client=chromadb.PersistentClient(path=str(tmp_path)))
    assert result.ok is False
    assert result.error_code == "RAG_UNAVAILABLE"


@pytest.mark.integration
def test_query_policy_finds_remote_monitor_allowance(tmp_path):
    import chromadb

    from onboard_pilot.tools.policy_rag import build_index

    client = chromadb.PersistentClient(path=str(tmp_path))
    try:
        build_index(client=client)
    except Exception as e:
        pytest.skip(f"embedding model unavailable: {e}")
    result = query_policy("monitor allowance remote", k=4, client=client)
    assert result.ok is True
    chunks = result.data["chunks"]
    assert "§6.4" in [c["section_id"] for c in chunks]
    assert all(0.0 <= c["score"] <= 1.0 for c in chunks)
    # rebuilding is idempotent
    assert build_index(client=client) == len(_chunks())
