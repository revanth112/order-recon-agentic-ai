# core/rules_rag.py - RAG over business rules and reconciliation guidelines
import re
import shutil
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from .config import (
    RULES_DIR,
    RAG_PERSIST_DIR,
    OPENAI_MODEL,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_EMBED_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
)

# Patterns that indicate code or non-text input
_CODE_PATTERNS = re.compile(
    r"("
    r"(def |class |import |from .+ import )"
    r"|(\bfunction\b\s+\w+\s*\(|\bconst\b\s+\w+\s*=)"
    r"|(SELECT\s+.+\s+FROM\s+)"
    r"|(<\s*/?\s*\w+[^>]*>)"
    r"|(\{\s*\".+\"\s*:\s*)"
    r"|(#include\s*<|int\s+main\s*\()"
    r"|(public\s+static\s+void\s+main)"
    r"|(\bfor\s*\(.*;\s*.*;\s*.*\))"
    r"|(=>|&&|\|\||!=|==)"
    r"|(```)"
    r")",
    re.IGNORECASE,
)

_vectorstore = None
_qa_chain = None


def _load_rules_docs() -> list[str]:
    """Load all markdown/txt files from the rules directory."""
    rules_path = Path(RULES_DIR)
    docs = []
    for path in sorted(rules_path.glob("*.md")):
        docs.append(path.read_text(encoding="utf-8"))
    for path in sorted(rules_path.glob("*.txt")):
        docs.append(path.read_text(encoding="utf-8"))
    return docs


def _build_embeddings() -> AzureOpenAIEmbeddings:
    return AzureOpenAIEmbeddings(
        azure_deployment=AZURE_EMBED_DEPLOYMENT,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version="2024-02-01",
    )


def init_rules_rag(force_reload: bool = False):
    """Initialize the RAG vectorstore and QA chain. Call once at startup."""
    global _vectorstore, _qa_chain

    if _qa_chain is not None and not force_reload:
        return  # already initialized

    persist_path = Path(RAG_PERSIST_DIR)

    # Detect stale Chroma index and wipe it so FAISS can start fresh
    chroma_marker = persist_path / "chroma.sqlite3"
    if chroma_marker.exists():
        shutil.rmtree(persist_path)
        # persist_path is now gone; the build-from-scratch path below will recreate it

    # ── Load or build the FAISS vectorstore ──────────────────────────────────
    faiss_index_file = persist_path / "index.faiss"

    if faiss_index_file.exists() and not force_reload:
        # Load existing FAISS index from disk.
        # allow_dangerous_deserialization is required by FAISS's load_local API;
        # the index is written exclusively by this application's save_local call.
        embeddings = _build_embeddings()
        _vectorstore = FAISS.load_local(
            str(persist_path),
            embeddings,
            allow_dangerous_deserialization=True,
        )
    else:
        # Build from scratch — check for docs before making any API calls
        raw_docs = _load_rules_docs()
        if not raw_docs:
            raise FileNotFoundError(
                f"No rules files found in '{RULES_DIR}'. Add .md files first."
            )

        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
        chunks = splitter.create_documents(raw_docs)

        # Wipe old index on force_reload
        if force_reload and persist_path.exists():
            shutil.rmtree(persist_path)
        persist_path.mkdir(parents=True, exist_ok=True)

        embeddings = _build_embeddings()
        _vectorstore = FAISS.from_documents(chunks, embeddings)
        _vectorstore.save_local(str(persist_path))

    retriever = _vectorstore.as_retriever(search_kwargs={"k": 3})

    # Azure Chat LLM
    llm = AzureChatOpenAI(
        azure_deployment=OPENAI_MODEL,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        temperature=0,
    )

    prompt_template = PromptTemplate(
        input_variables=["context", "question"],
        template=(
            "You are a reconciliation rules expert.\n"
            "Use ONLY the following business rules to answer the question.\n"
            "If the provided rules do not contain information relevant to the "
            "question, respond exactly with: Sorry, I'm not aware of it.\n"
            "Do NOT make up or guess any information that is not in the rules.\n\n"
            "{context}\n\n"
            "Question: {question}\n"
            "Answer concisely and cite the rule name if applicable:"
        ),
    )

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    _qa_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt_template
        | llm
        | StrOutputParser()
    )


def validate_input(question: str) -> str:
    """Validate that the input is plain text, not code or other non-text content."""
    text = question.strip()
    if not text:
        raise ValueError("Please enter a question.")
    if _CODE_PATTERNS.search(text):
        raise ValueError(
            "Only plain text questions are accepted. "
            "Please remove any code, HTML, or special syntax."
        )
    return text


def ask_rules(question: str) -> str:
    """Query the RAG chain with a reconciliation question."""
    cleaned = validate_input(question)
    if _qa_chain is None:
        init_rules_rag()
    return _qa_chain.invoke(cleaned)


def reload_rules():
    """Force reload RAG index (call after updating rules files)."""
    init_rules_rag(force_reload=True)
