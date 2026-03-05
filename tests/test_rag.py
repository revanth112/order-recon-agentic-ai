# tests/test_rag.py
# Unit tests for the RAG system (core/rules_rag.py)
# All tests use mocks - NO Azure OpenAI API key required to run.
#
# Test coverage:
#   1. _load_rules_docs()    - loads .md and .txt files from rules dir
#   2. _load_rules_docs()    - returns empty list if no files exist
#   3. init_rules_rag()      - skips rebuild when chain already loaded
#   4. init_rules_rag()      - raises FileNotFoundError when no docs found
#   5. init_rules_rag()      - builds vectorstore and LCEL chain correctly
#   6. ask_rules()           - auto-inits on first call
#   7. ask_rules()           - calls chain.invoke() with the exact question
#   8. ask_rules()           - always returns a string
#   9. reload_rules()        - calls init_rules_rag(force_reload=True)

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _write_temp_rules(tmp_path, files: dict):
    """Write fake rule files into a temp directory."""
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# 1 & 2 - _load_rules_docs()
# ---------------------------------------------------------------------------

def test_load_rules_docs_reads_md_and_txt(tmp_path, monkeypatch):
    """Should load content from both .md and .txt files in RULES_DIR."""
    _write_temp_rules(tmp_path, {
        "rule1.md": "# Price Rule\nInvoice price must match PO.",
        "rule2.txt": "Quantity tolerance is 5%.",
    })

    import importlib
    import core.config as cfg
    monkeypatch.setattr(cfg, "RULES_DIR", str(tmp_path))

    import core.rules_rag as rag
    importlib.reload(rag)

    docs = rag._load_rules_docs()
    assert len(docs) == 2
    assert any("Price Rule" in d for d in docs)
    assert any("Quantity tolerance" in d for d in docs)


def test_load_rules_docs_returns_empty_when_no_files(tmp_path, monkeypatch):
    """Should return an empty list when the rules directory is empty."""
    import importlib
    import core.config as cfg
    monkeypatch.setattr(cfg, "RULES_DIR", str(tmp_path))

    import core.rules_rag as rag
    importlib.reload(rag)

    docs = rag._load_rules_docs()
    assert docs == []


# ---------------------------------------------------------------------------
# 3 & 4 & 5 - init_rules_rag()
# ---------------------------------------------------------------------------

def test_init_rules_rag_skips_if_already_initialised():
    """Should not rebuild chain if _qa_chain is already set."""
    import importlib
    import core.rules_rag as rag
    importlib.reload(rag)

    fake_chain = MagicMock()
    rag._qa_chain = fake_chain

    with patch.object(rag, "_load_rules_docs") as mock_load:
        rag.init_rules_rag(force_reload=False)
        mock_load.assert_not_called()
    assert rag._qa_chain is fake_chain


def test_init_rules_rag_raises_when_no_docs():
    """Should raise FileNotFoundError when _load_rules_docs returns []."""
    import importlib
    import core.rules_rag as rag
    importlib.reload(rag)
    rag._qa_chain = None

    with patch.object(rag, "_load_rules_docs", return_value=[]):
        with pytest.raises(FileNotFoundError, match="No rules files found"):
            rag.init_rules_rag()


@patch("core.rules_rag.RunnablePassthrough")
@patch("core.rules_rag.StrOutputParser")
@patch("core.rules_rag.AzureChatOpenAI")        # Updated: was ChatOpenAI
@patch("core.rules_rag.PromptTemplate")
@patch("core.rules_rag.Chroma")
@patch("core.rules_rag.AzureOpenAIEmbeddings")  # Updated: was OpenAIEmbeddings
@patch("core.rules_rag.RecursiveCharacterTextSplitter")
def test_init_rules_rag_builds_chain_correctly(
    MockSplitter,
    MockEmbeddings,
    MockChroma,
    MockPrompt,
    MockLLM,
    MockParser,
    MockPassthrough,
):
    """Should create vectorstore and set _qa_chain when docs are present."""
    import importlib
    import core.rules_rag as rag
    importlib.reload(rag)

    rag._qa_chain = None
    rag._vectorstore = None

    fake_doc = MagicMock()
    fake_doc.page_content = "Price must match PO."
    MockSplitter.return_value.create_documents.return_value = [fake_doc]
    MockChroma.from_documents.return_value.as_retriever.return_value = MagicMock()

    with patch.object(rag, "_load_rules_docs", return_value=["Price must match PO."]):
        rag.init_rules_rag()

    MockChroma.from_documents.assert_called_once()
    MockLLM.assert_called_once()
    assert rag._qa_chain is not None


# ---------------------------------------------------------------------------
# 6, 7 & 8 - ask_rules()
# ---------------------------------------------------------------------------

def test_ask_rules_auto_inits_on_first_call():
    """ask_rules() should call init_rules_rag() when _qa_chain is None."""
    import importlib
    import core.rules_rag as rag
    importlib.reload(rag)
    rag._qa_chain = None

    fake_chain = MagicMock()
    fake_chain.invoke.return_value = "Prices must match within 5%."

    def side_effect():
        rag._qa_chain = fake_chain

    with patch.object(rag, "init_rules_rag", side_effect=side_effect) as mock_init:
        result = rag.ask_rules("What is the price tolerance?")
        mock_init.assert_called_once()
    assert result == "Prices must match within 5%."


def test_ask_rules_calls_invoke_with_exact_question():
    """ask_rules() must call chain.invoke() with the exact question string."""
    import importlib
    import core.rules_rag as rag
    importlib.reload(rag)

    fake_chain = MagicMock()
    fake_chain.invoke.return_value = "Flag as CRITICAL exception."
    rag._qa_chain = fake_chain

    question = "What happens when product code is not in any open PO?"
    result = rag.ask_rules(question)
    fake_chain.invoke.assert_called_once_with(question)
    assert result == "Flag as CRITICAL exception."


def test_ask_rules_returns_string():
    """ask_rules() should always return a string."""
    import importlib
    import core.rules_rag as rag
    importlib.reload(rag)

    fake_chain = MagicMock()
    fake_chain.invoke.return_value = "Apply 2% tolerance for Global Tech Corp."
    rag._qa_chain = fake_chain

    result = rag.ask_rules("Vendor policy for Global Tech Corp?")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 9 - reload_rules()
# ---------------------------------------------------------------------------

def test_reload_rules_calls_init_with_force_reload_true():
    """reload_rules() must call init_rules_rag(force_reload=True)."""
    import importlib
    import core.rules_rag as rag
    importlib.reload(rag)

    with patch.object(rag, "init_rules_rag") as mock_init:
        rag.reload_rules()
        mock_init.assert_called_once_with(force_reload=True)
