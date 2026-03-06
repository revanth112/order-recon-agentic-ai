# core/rules_rag.py - RAG over business rules and reconciliation guidelines
import re
import json
import hashlib
import numpy as np
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
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

_qa_chain = None
_chunks: list[str] = []
_embeddings_matrix: np.ndarray | None = None  # shape: (N, dim)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_rules_docs() -> list[str]:
    rules_path = Path(RULES_DIR)
    docs = []
    for path in sorted(rules_path.glob("*.md")):
        docs.append(path.read_text(encoding="utf-8"))
    for path in sorted(rules_path.glob("*.txt")):
        docs.append(path.read_text(encoding="utf-8"))
    return docs


def _build_embeddings_client() -> AzureOpenAIEmbeddings:
    return AzureOpenAIEmbeddings(
        azure_deployment=AZURE_EMBED_DEPLOYMENT,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version="2024-02-01",
    )


def _index_path() -> Path:
    return Path(RAG_PERSIST_DIR)


def _save_index(chunks: list[str], matrix: np.ndarray):
    path = _index_path()
    path.mkdir(parents=True, exist_ok=True)
    (path / "chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    np.save(str(path / "embeddings.npy"), matrix)


def _load_index() -> tuple[list[str], np.ndarray] | None:
    path = _index_path()
    chunks_file = path / "chunks.json"
    emb_file    = path / "embeddings.npy"
    if chunks_file.exists() and emb_file.exists():
        chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
        matrix = np.load(str(emb_file))
        return chunks, matrix
    return None


def _cosine_similarity(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Return cosine similarity between query_vec (1-D) and each row of matrix."""
    q = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
    normed = matrix / norms
    return normed @ q


def _retrieve(question: str, k: int = 3) -> str:
    """Return top-k relevant chunks for the question as a single string."""
    global _chunks, _embeddings_matrix
    embed_client = _build_embeddings_client()
    q_vec = np.array(embed_client.embed_query(question), dtype=np.float32)
    sims  = _cosine_similarity(q_vec, _embeddings_matrix)
    top_k = np.argsort(sims)[::-1][:k]
    return "\n\n".join(_chunks[i] for i in top_k)


# ── Public API ────────────────────────────────────────────────────────────────

def init_rules_rag(force_reload: bool = False):
    """Initialize the RAG index and QA chain."""
    global _qa_chain, _chunks, _embeddings_matrix

    if _qa_chain is not None and not force_reload:
        return

    # ── Try loading persisted index ───────────────────────────────────────────
    loaded = None if force_reload else _load_index()

    if loaded is not None:
        _chunks_list, _embeddings_matrix = loaded
        _chunks = _chunks_list
    else:
        # Build from scratch
        raw_docs = _load_rules_docs()
        if not raw_docs:
            raise FileNotFoundError(
                f"No rules files found in '{RULES_DIR}'. Add .md files first."
            )

        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
        doc_chunks = splitter.create_documents(raw_docs)
        _chunks = [d.page_content for d in doc_chunks]

        embed_client = _build_embeddings_client()
        # embed_documents returns list[list[float]] — safe plain Python lists
        vectors = embed_client.embed_documents(_chunks)
        _embeddings_matrix = np.array(vectors, dtype=np.float32)

        _save_index(_chunks, _embeddings_matrix)

    # ── Build QA chain ────────────────────────────────────────────────────────
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

    def build_input(question: str) -> dict:
        return {
            "context":  _retrieve(question),
            "question": question,
        }

    _qa_chain = (
        RunnableLambda(build_input)
        | prompt_template
        | llm
        | StrOutputParser()
    )


def validate_input(question: str) -> str:
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
    cleaned = validate_input(question)
    if _qa_chain is None:
        init_rules_rag()
    return _qa_chain.invoke(cleaned)


def reload_rules():
    """Force reload RAG index (call after updating rules files)."""
    init_rules_rag(force_reload=True)
