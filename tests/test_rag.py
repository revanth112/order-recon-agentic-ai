# tests/test_rag.py
# Integration tests for the RAG system (core/rules_rag.py)
# Uses REAL Azure OpenAI API - requires .env to be configured.
#
# Run with:
#   pytest tests/test_rag.py -v
#
# Test coverage:
#   1. _load_rules_docs()  - loads real .md and .txt files from rules dir
#   2. _load_rules_docs()  - returns empty list if directory is empty
#   3. init_rules_rag()    - skips rebuild when chain already loaded
#   4. init_rules_rag()    - raises FileNotFoundError when no docs found
#   5. init_rules_rag()    - builds real vectorstore + LCEL chain (hits Azure)
#   6. ask_rules()         - returns a real non-empty string answer from Azure
#   7. ask_rules()         - answer is relevant to the question asked
#   8. ask_rules()         - auto-inits on first call (cold start)
#   9. reload_rules()      - rebuilds the chain from scratch (force reload)

import importlib
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_temp_rules(tmp_path, files: dict):
    """Write real rule content into a temp directory for isolated tests."""
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")


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
        "Over-shipments must be flagged for return or credit note.\n"
        "Rule Name: QTY_TOLERANCE_5PCT\n"
    ),
    "no_match_rules.txt": (
        "NO_MATCH Rule: If a product code on the invoice does not exist in any\n"
        "open Purchase Order, the line must be BLOCKED and raised as a\n"
        "CRITICAL exception requiring immediate procurement review.\n"
        "Rule Name: NO_MATCH_CRITICAL\n"
    ),
}


# ---------------------------------------------------------------------------
# 1 & 2 - _load_rules_docs() -- pure file I/O, no API needed
# ---------------------------------------------------------------------------

def test_load_rules_docs_reads_md_and_txt(tmp_path, monkeypatch):
    """Should load content from all .md and .txt files in RULES_DIR."""
    _write_temp_rules(tmp_path, SAMPLE_RULES)

    import core.config as cfg
    monkeypatch.setattr(cfg, "RULES_DIR", str(tmp_path))

    import core.rules_rag as rag
    importlib.reload(rag)

    docs = rag._load_rules_docs()
    assert len(docs) == 3
    assert any("Price Matching Rule" in d for d in docs)
    assert any("Quantity Matching Rule" in d for d in docs)
    assert any("NO_MATCH Rule" in d for d in docs)


def test_load_rules_docs_returns_empty_when_no_files(tmp_path, monkeypatch):
    """Should return an empty list when the rules directory is empty."""
    import core.config as cfg
    monkeypatch.setattr(cfg, "RULES_DIR", str(tmp_path))

    import core.rules_rag as rag
    importlib.reload(rag)

    docs = rag._load_rules_docs()
    assert docs == []


# ---------------------------------------------------------------------------
# 3 - init_rules_rag() skips rebuild -- no API needed
# ---------------------------------------------------------------------------

def test_init_rules_rag_skips_if_already_initialised():
    """Should not rebuild chain if _qa_chain is already set."""
    import core.rules_rag as rag
    importlib.reload(rag)

    # Simulate an already-built chain with a sentinel object
    sentinel = object()
    rag._qa_chain = sentinel

    rag.init_rules_rag(force_reload=False)

    # Chain must remain unchanged - no rebuild happened
    assert rag._qa_chain is sentinel


# ---------------------------------------------------------------------------
# 4 - init_rules_rag() raises when no docs -- no API needed
# ---------------------------------------------------------------------------

def test_init_rules_rag_raises_when_no_docs(tmp_path, monkeypatch):
    """Should raise FileNotFoundError when rules dir has no files."""
    import core.config as cfg
    monkeypatch.setattr(cfg, "RULES_DIR", str(tmp_path))
    monkeypatch.setattr(cfg, "RAG_PERSIST_DIR", str(tmp_path / "index"))

    import core.rules_rag as rag
    importlib.reload(rag)
    rag._qa_chain = None

    with pytest.raises(FileNotFoundError, match="No rules files found"):
        rag.init_rules_rag()


# ---------------------------------------------------------------------------
# 5 - init_rules_rag() builds real chain -- HITS AZURE API
# ---------------------------------------------------------------------------

def test_init_rules_rag_builds_real_chain(tmp_path, monkeypatch):
    """
    Real integration test: builds vectorstore with Azure OpenAI embeddings
    and constructs the LCEL chain. Requires .env to be configured.
    """
    _write_temp_rules(tmp_path, SAMPLE_RULES)

    import core.config as cfg
    monkeypatch.setattr(cfg, "RULES_DIR", str(tmp_path))
    monkeypatch.setattr(cfg, "RAG_PERSIST_DIR", str(tmp_path / "index"))

    import core.rules_rag as rag
    importlib.reload(rag)
    rag._qa_chain = None
    rag._vectorstore = None

    # This makes real Azure OpenAI embedding API calls
    rag.init_rules_rag()

    assert rag._qa_chain is not None, "Chain must be built after init_rules_rag()"
    assert rag._vectorstore is not None, "Vectorstore must be populated"


# ---------------------------------------------------------------------------
# 6 & 7 - ask_rules() returns a real answer -- HITS AZURE API
# ---------------------------------------------------------------------------

def test_ask_rules_returns_real_answer_for_price_question(tmp_path, monkeypatch):
    """
    Real integration test: asks a price-related question and checks
    that Azure returns a non-empty string answer.
    """
    _write_temp_rules(tmp_path, SAMPLE_RULES)

    import core.config as cfg
    monkeypatch.setattr(cfg, "RULES_DIR", str(tmp_path))
    monkeypatch.setattr(cfg, "RAG_PERSIST_DIR", str(tmp_path / "index"))

    import core.rules_rag as rag
    importlib.reload(rag)
    rag._qa_chain = None
    rag._vectorstore = None

    answer = rag.ask_rules(
        "What is the tolerance rule when invoice price differs from PO price?"
    )

    assert isinstance(answer, str), "Answer must be a string"
    assert len(answer.strip()) > 10, "Answer must be non-trivial"
    # The answer should mention tolerance or price or 5%
    keywords = ["tolerance", "price", "5%", "PRICE_TOLERANCE", "finance"]
    assert any(kw.lower() in answer.lower() for kw in keywords), (
        f"Expected answer to be relevant to price tolerance, got: {answer}"
    )


def test_ask_rules_returns_real_answer_for_no_match_question(tmp_path, monkeypatch):
    """
    Real integration test: asks a NO_MATCH scenario question and
    validates the response references blocking or critical exceptions.
    """
    _write_temp_rules(tmp_path, SAMPLE_RULES)

    import core.config as cfg
    monkeypatch.setattr(cfg, "RULES_DIR", str(tmp_path))
    monkeypatch.setattr(cfg, "RAG_PERSIST_DIR", str(tmp_path / "index"))

    import core.rules_rag as rag
    importlib.reload(rag)
    rag._qa_chain = None
    rag._vectorstore = None

    answer = rag.ask_rules(
        "What should happen when a product code on the invoice is not found in any PO?"
    )

    assert isinstance(answer, str)
    assert len(answer.strip()) > 10
    keywords = ["block", "critical", "exception", "procurement", "NO_MATCH"]
    assert any(kw.lower() in answer.lower() for kw in keywords), (
        f"Expected answer to reference blocking/critical, got: {answer}"
    )


# ---------------------------------------------------------------------------
# 8 - ask_rules() cold start (auto-init) -- HITS AZURE API
# ---------------------------------------------------------------------------

def test_ask_rules_cold_start_auto_inits(tmp_path, monkeypatch):
    """
    ask_rules() must auto-initialize the chain on first call
    even when _qa_chain is None (cold start scenario).
    """
    _write_temp_rules(tmp_path, SAMPLE_RULES)

    import core.config as cfg
    monkeypatch.setattr(cfg, "RULES_DIR", str(tmp_path))
    monkeypatch.setattr(cfg, "RAG_PERSIST_DIR", str(tmp_path / "index"))

    import core.rules_rag as rag
    importlib.reload(rag)
    rag._qa_chain = None   # Force cold start
    rag._vectorstore = None

    # ask_rules should auto-call init_rules_rag internally
    answer = rag.ask_rules("What is the quantity tolerance rule?")

    assert rag._qa_chain is not None, "Chain must be initialized after cold-start ask"
    assert isinstance(answer, str)
    assert len(answer.strip()) > 5


# ---------------------------------------------------------------------------
# 9 - reload_rules() rebuilds from scratch -- HITS AZURE API
# ---------------------------------------------------------------------------

def test_reload_rules_rebuilds_chain(tmp_path, monkeypatch):
    """
    reload_rules() must force a full rebuild of the vectorstore and chain,
    even if the chain was already initialised.
    """
    _write_temp_rules(tmp_path, SAMPLE_RULES)

    import core.config as cfg
    monkeypatch.setattr(cfg, "RULES_DIR", str(tmp_path))
    monkeypatch.setattr(cfg, "RAG_PERSIST_DIR", str(tmp_path / "index"))

    import core.rules_rag as rag
    importlib.reload(rag)
    rag._qa_chain = None
    rag._vectorstore = None

    # First build
    rag.init_rules_rag()
    first_chain = rag._qa_chain
    assert first_chain is not None

    # Force reload - must create a NEW chain object
    rag.reload_rules()
    second_chain = rag._qa_chain

    assert second_chain is not None
    # After reload a new chain object is built
    assert second_chain is not first_chain, (
        "reload_rules() must create a new chain, not reuse the old one"
    )
