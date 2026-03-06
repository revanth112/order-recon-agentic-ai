# tests/test_rules_rag.py
# Unit tests for core/rules_rag.py (FAISS-based implementation)
# All Azure API calls are mocked — no real credentials needed.
#
# Run with:
#   pytest tests/test_rules_rag.py -v
#
# Test coverage:
#   1. init_rules_rag() runs without error (mocked embeddings + FAISS)
#   2. ask_rules() returns a string
#   3. validate_input("") raises ValueError
#   4. validate_input("SELECT * FROM table") raises ValueError (code pattern)
#   5. reload_rules() runs without error (force_reload path)

import importlib
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Sample rules content used across tests
# ---------------------------------------------------------------------------

SAMPLE_RULES = {
    "price_rules.md": (
        "# Price Matching Rule\n"
        "Invoice unit price must match the PO unit price within 5% tolerance.\n"
        "Deviations above 5% must be escalated to finance team for approval.\n"
        "Rule Name: PRICE_TOLERANCE_5PCT\n"
    ),
    "qty_rules.md": (
        "# Quantity Matching Rule\n"
        "Invoice quantity must match ordered quantity within 5% tolerance.\n"
        "Short shipments under 5% can be auto-approved.\n"
        "Rule Name: QTY_TOLERANCE_5PCT\n"
    ),
}


def _write_temp_rules(tmp_path, files: dict):
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Shared mock factory
# ---------------------------------------------------------------------------

def _make_mock_embeddings():
    """Return a mock AzureOpenAIEmbeddings that returns dummy float vectors."""
    mock_emb = MagicMock()
    # Return one embedding vector per input document (length-matched)
    mock_emb.embed_documents.side_effect = lambda texts: [[0.1, 0.2, 0.3]] * len(texts)
    mock_emb.embed_query.return_value = [0.1, 0.2, 0.3]
    return mock_emb


def _make_mock_llm():
    """Return a mock AzureChatOpenAI whose invoke returns a fixed string."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="The quantity tolerance is 5%.")
    return mock_llm


# ---------------------------------------------------------------------------
# 1 - init_rules_rag() runs without error
# ---------------------------------------------------------------------------

def test_init_rules_rag_runs_without_error(tmp_path, monkeypatch):
    """init_rules_rag() should complete without error when Azure calls are mocked."""
    _write_temp_rules(tmp_path, SAMPLE_RULES)

    import core.config as cfg
    monkeypatch.setattr(cfg, "RULES_DIR", str(tmp_path))
    monkeypatch.setattr(cfg, "RAG_PERSIST_DIR", str(tmp_path / "index"))

    import core.rules_rag as rag
    importlib.reload(rag)
    rag._qa_chain = None
    rag._vectorstore = None

    mock_emb = _make_mock_embeddings()

    with (
        patch("core.rules_rag._build_embeddings", return_value=mock_emb),
        patch("core.rules_rag.AzureChatOpenAI", return_value=_make_mock_llm()),
    ):
        rag.init_rules_rag()

    assert rag._qa_chain is not None
    assert rag._vectorstore is not None


# ---------------------------------------------------------------------------
# 2 - ask_rules() returns a string
# ---------------------------------------------------------------------------

def test_ask_rules_returns_string(tmp_path, monkeypatch):
    """ask_rules() should return a string answer."""
    _write_temp_rules(tmp_path, SAMPLE_RULES)

    import core.config as cfg
    monkeypatch.setattr(cfg, "RULES_DIR", str(tmp_path))
    monkeypatch.setattr(cfg, "RAG_PERSIST_DIR", str(tmp_path / "index"))

    import core.rules_rag as rag
    importlib.reload(rag)
    rag._qa_chain = None
    rag._vectorstore = None

    mock_emb = _make_mock_embeddings()

    with (
        patch("core.rules_rag._build_embeddings", return_value=mock_emb),
        patch("core.rules_rag.AzureChatOpenAI", return_value=_make_mock_llm()),
    ):
        rag.init_rules_rag()

    # Replace the fully-built chain with a simple mock that returns a fixed string
    rag._qa_chain = MagicMock()
    rag._qa_chain.invoke.return_value = "The quantity tolerance is 5%."

    result = rag.ask_rules("What is the quantity tolerance?")

    assert isinstance(result, str)
    assert result == "The quantity tolerance is 5%."


# ---------------------------------------------------------------------------
# 3 - validate_input("") raises ValueError
# ---------------------------------------------------------------------------

def test_validate_input_empty_raises():
    """validate_input should raise ValueError for empty input."""
    import core.rules_rag as rag
    importlib.reload(rag)

    with pytest.raises(ValueError, match="Please enter a question"):
        rag.validate_input("")

    with pytest.raises(ValueError, match="Please enter a question"):
        rag.validate_input("   ")


# ---------------------------------------------------------------------------
# 4 - validate_input("SELECT * FROM table") raises ValueError
# ---------------------------------------------------------------------------

def test_validate_input_sql_raises():
    """validate_input should reject SQL code patterns."""
    import core.rules_rag as rag
    importlib.reload(rag)

    with pytest.raises(ValueError, match="Only plain text questions are accepted"):
        rag.validate_input("SELECT * FROM table")


# ---------------------------------------------------------------------------
# 5 - reload_rules() runs without error (force_reload path)
# ---------------------------------------------------------------------------

def test_reload_rules_runs_without_error(tmp_path, monkeypatch):
    """reload_rules() should force-rebuild the chain without error."""
    _write_temp_rules(tmp_path, SAMPLE_RULES)

    import core.config as cfg
    monkeypatch.setattr(cfg, "RULES_DIR", str(tmp_path))
    monkeypatch.setattr(cfg, "RAG_PERSIST_DIR", str(tmp_path / "index"))

    import core.rules_rag as rag
    importlib.reload(rag)
    rag._qa_chain = None
    rag._vectorstore = None

    mock_emb = _make_mock_embeddings()

    with (
        patch("core.rules_rag._build_embeddings", return_value=mock_emb),
        patch("core.rules_rag.AzureChatOpenAI", return_value=_make_mock_llm()),
    ):
        rag.reload_rules()

    assert rag._qa_chain is not None
    assert rag._vectorstore is not None
