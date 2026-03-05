# core/rules_rag.py - RAG over business rules and reconciliation guidelines
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate
from .config import RULES_DIR, RAG_PERSIST_DIR, OPENAI_MODEL

_vectorstore = None
_qa_chain = None


def _load_rules_docs() -> list[str]:
    """Load all markdown/txt files from the rules directory."""
    rules_path = Path(RULES_DIR)
    docs = []
    for path in rules_path.glob("*.md"):
        docs.append(path.read_text(encoding="utf-8"))
    for path in rules_path.glob("*.txt"):
        docs.append(path.read_text(encoding="utf-8"))
    return docs


def init_rules_rag(force_reload: bool = False):
    """Initialize the RAG vectorstore and QA chain. Call once at startup."""
    global _vectorstore, _qa_chain

    if _qa_chain is not None and not force_reload:
        return  # already initialized

    raw_docs = _load_rules_docs()
    if not raw_docs:
        raise FileNotFoundError(f"No rules files found in '{RULES_DIR}'. Add .md files first.")

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    chunks = splitter.create_documents(raw_docs)

    embeddings = OpenAIEmbeddings()
    _vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=RAG_PERSIST_DIR,
    )

    retriever = _vectorstore.as_retriever(search_kwargs={"k": 3})

    prompt_template = PromptTemplate(
        input_variables=["context", "question"],
        template=(
            "You are a reconciliation rules expert.\n"
            "Use the following business rules to answer the question:\n\n"
            "{context}\n\n"
            "Question: {question}\n"
            "Answer concisely and cite the rule name if applicable:"
        ),
    )

    llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0)
    _qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": prompt_template},
        return_source_documents=False,
    )


def ask_rules(question: str) -> str:
    """Query the RAG chain with a reconciliation question. Auto-initializes on first call."""
    if _qa_chain is None:
        init_rules_rag()
    return _qa_chain.run(question)


def reload_rules():
    """Force reload RAG index (call after updating rules files)."""
    init_rules_rag(force_reload=True)
