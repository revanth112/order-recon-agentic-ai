# Order Reconciliation Agentic AI

> **Multi-Agent Order Reconciliation System** using LangGraph, Azure OpenAI (AI Foundry), ChromaDB (RAG), SQLite and Streamlit

---

## Problem Statement

Finance and operations teams reconcile invoices, Purchase Orders (POs), and delivery records **manually** — a process that is slow, error-prone, and causes delays in month-end closing.

## Solution

A **multi-agent AI system** that:
- Accepts invoice JSON as input
- Extracts structured fields using Azure OpenAI GPT-4o
- Matches invoices to POs using configurable tolerance rules
- Identifies discrepancies (price, quantity, product codes)
- Auto-updates a simulated SQLite order database
- Generates exception reports via a Streamlit UI
- Provides full observability (mismatch metrics, pipeline traces)

---

## Architecture

```
Invoice JSON Input
        |
        v
[Extractor Agent]  <-- Azure OpenAI GPT-4o structured extraction + Pydantic validation
        |
        v
[Matcher Agent]    <-- Rule-based matching + RAG on business rules (ChromaDB)
        |
        v
[Exception Handler] <-- Auto-approve / block / flag for human review
        |
        v
[SQLite DB]  +  [Streamlit UI Dashboard]
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| LLM | Azure OpenAI GPT-4o (via Azure AI Foundry) |
| Embeddings | Azure OpenAI text-embedding-ada-002 |
| Agent Framework | LangGraph |
| RAG | LangChain + ChromaDB |
| Database | SQLite |
| UI | Streamlit |
| Validation | Pydantic v2 |

---

## Project Structure

```
order-recon-agentic-ai/
├── agents/           # LangGraph nodes (extractor, matcher, exception handler)
├── core/             # Business logic, config, db, repositories, RAG, logger
├── data/             # SQLite DB + ChromaDB vector index
├── models/           # Pydantic schemas
├── rules/            # Business rules markdown files (RAG source)
├── scripts/          # Data generation scripts
├── streamlit_app/    # UI pages (dashboard, log viewer)
├── tests/            # Pytest test suite
├── .env              # Environment variables (not committed)
└── requirements.txt
```

---

## Setup

### 1. Clone & Install

```bash
git clone https://github.com/revanth112/order-recon-agentic-ai.git
cd order-recon-agentic-ai
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
# -------------------------------------------------------
# Azure AI Foundry - OpenAI SDK v1.x with Azure base_url
# -------------------------------------------------------
AZURE_OPENAI_API_KEY=your-azure-openai-api-key-here
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE-NAME.openai.azure.com/openai/v1/

# Deployment names (as set in Azure AI Foundry)
AZURE_CHAT_DEPLOYMENT=gpt-4o
AZURE_EMBED_DEPLOYMENT=text-embedding-ada-002

# Database
SQLITE_DB_PATH=./data/order_recon.db

# Reconciliation thresholds
CONFIDENCE_THRESHOLD=0.8
PRICE_TOLERANCE_PCT=0.05
QTY_TOLERANCE_PCT=0.05

# RAG paths
RULES_DIR=./rules
RAG_PERSIST_DIR=./data/rules_index

# App settings
ENV=dev
LOG_LEVEL=INFO
```

> **Where to find your Azure credentials:**
> 1. Go to [Azure AI Foundry](https://ai.azure.com) → your project
> 2. **Deployments** tab → note your deployment name (e.g., `gpt-4o`)
> 3. **Overview** → copy the **Endpoint** and **API Key**

### 3. Initialize the Database & Generate Data

```bash
python scripts/generate_data.py
```

### 4. Run the Streamlit UI

```bash
streamlit run streamlit_app/app.py
```

Open [http://localhost:8501](http://localhost:8501)

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# Individual test modules
pytest tests/test_db.py -v
pytest tests/test_extract.py -v
pytest tests/test_match.py -v
pytest tests/test_logging.py -v
pytest tests/test_rag.py -v
```

---

## Core Features

### Extractor Agent
- Sends invoice JSON to Azure OpenAI GPT-4o
- Parses structured output with Pydantic (`ExtractedInvoice`)
- Scores extraction confidence; flags low-confidence runs

### Matcher Agent
- Matches invoice lines to order lines by `product_code`
- Applies configurable `PRICE_TOLERANCE_PCT` and `QTY_TOLERANCE_PCT`
- Queries ChromaDB RAG for applicable business rules on mismatches

### Exception Handler
- Classifies exceptions as `CRITICAL` (NO_MATCH) or `WARNING`
- Auto-actions: `BLOCKED` or `NEEDS_REVIEW`
- Stores all exceptions in SQLite for audit trail

### RAG on Business Rules
- Markdown rule files in `rules/` directory
- Indexed with Azure OpenAI embeddings into ChromaDB
- Retrieved at match-time to provide context-aware rule citations

### Observability
- Pipeline logs stored in `pipeline_logs` table
- Streamlit log viewer with run_id filtering
- Mismatch metrics dashboard with charts

---

## License

MIT
