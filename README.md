# Order Reconciliation Agentic AI

> **Multi-Agent Order Reconciliation System** using LangGraph, Azure OpenAI (AI Foundry), FAISS (RAG), SQLite and Streamlit

---

## Problem Statement

Finance and operations teams reconcile invoices, Purchase Orders (POs), and delivery records **manually** — a process that is slow, error-prone, and causes delays in month-end closing.

## Solution

A **multi-agent AI system** that:
- Accepts invoice JSON as input
- Extracts structured fields using Azure OpenAI GPT-4o + Pydantic validation
- Matches invoices to POs using configurable tolerance rules
- Identifies discrepancies (price, quantity, product codes, currency)
- Auto-approves, blocks, or flags invoices for human review
- Persists all data to a SQLite order database
- Generates exception reports via a Streamlit UI
- Provides full observability (mismatch metrics, pipeline traces)

---

## Architecture

```
Invoice JSON Input
        |
        v
[Extractor Agent]    <-- Azure OpenAI GPT-4o structured extraction + Pydantic validation
        |
        v
[Matcher Agent]      <-- Rule-based matching + RAG on business rules (FAISS + LangChain)
        |
        v
[Exception Handler]  <-- Auto-approve / block / flag for human review
        |
        v
[SQLite DB]  +  [Streamlit UI Dashboard (7 pages)]
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| LLM | Azure OpenAI GPT-4o (via Azure AI Foundry) |
| Embeddings | Azure OpenAI text-embedding-ada-002 |
| Agent Framework | LangGraph (StateGraph) |
| RAG | LangChain + FAISS (local vector index) |
| Database | SQLite (built-in Python) |
| UI | Streamlit |
| Validation | Pydantic v2 |
| Data | Pandas, NumPy |
| Visualisation | Plotly |

---

## Project Structure

```
order-recon-agentic-ai/
├── streamlit_app/          ← UI Layer
│   ├── app.py              ← Main Streamlit app (7 pages)
│   └── log_viewer.py       ← Pipeline log viewer component
├── agents/                 ← LangGraph Agent Layer
│   ├── graph.py            ← Builds & compiles the LangGraph StateGraph
│   ├── nodes.py            ← 3 agent node functions
│   └── state.py            ← ReconState TypedDict (shared state)
├── core/                   ← Business Logic Layer
│   ├── config.py           ← Env vars, Azure OpenAI client, thresholds
│   ├── db.py               ← SQLite schema init & connection manager
│   ├── repositories.py     ← All DB CRUD operations
│   ├── services.py         ← Extractor & Matcher business logic
│   ├── rules_rag.py        ← RAG engine (FAISS + embeddings + LangChain)
│   ├── metrics.py          ← Observability metrics computation
│   └── logger.py           ← Pipeline log persistence to SQLite
├── models/
│   └── schemas.py          ← Pydantic models: ExtractedInvoice, InvoiceLine
├── rules/                  ← RAG Knowledge Base
│   ├── reconciliation_rules.md
│   ├── vendor_policies.md
│   └── rag_training_docs.md
├── data/                   ← Runtime Data (git-ignored)
│   ├── order_recon.db      ← SQLite database
│   ├── demo_invoices/      ← 15 ready-to-upload test invoice JSONs
│   └── rules_index/        ← FAISS vector index
├── scripts/
│   └── seed_data.py        ← Seeds demo POs and orders into SQLite
├── tests/                  ← Pytest test suite
├── requirements.txt
└── .env                    ← Environment variables (not committed)
```

---

## Streamlit UI Pages

| Page | Description |
|------|-------------|
| 🚀 Upload & Run Pipeline | Upload invoice JSON, run multi-agent pipeline with live stepper |
| 🗄️ Database Explorer | Browse & filter all SQLite tables; export CSV |
| 📦 Order Tracker | Invoice history, reconciliation details, pipeline logs |
| ⚠️ Exceptions Dashboard | Unresolved & all exceptions; filter, resolve, export |
| 🧠 RAG Management | View business rules documents loaded into the RAG index |
| 📈 Observability Metrics | Mismatch rate, confidence, latency charts |
| 🏗️ Project Architecture | Full system overview, folder structure, DB schema, tech stack |

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
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE-NAME.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-12-01

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

### 3. Initialize the Database & Generate Demo Data

```bash
python scripts/seed_data.py
```

This seeds 15 demo Purchase Orders (`DEMO-PO-001` … `DEMO-PO-015`) that match the invoice files in `data/demo_invoices/`.

### 4. Run the Streamlit UI

```bash
streamlit run streamlit_app/app.py
```

Open [http://localhost:8501](http://localhost:8501)

---

## Demo Invoices

The `data/demo_invoices/` folder contains **15 ready-to-upload invoice JSON files** covering every reconciliation outcome:

| # | Scenario | Outcome | Exception Type | Severity |
|---|----------|---------|----------------|----------|
| 01 | Perfect Match | ✅ MATCHED | — | — |
| 02 | Within Tolerance | ✅ MATCHED | TOLERANCE_VARIANCE | INFO |
| 03 | Quantity Mismatch | ⚠️ MISMATCH | QUANTITY_MISMATCH | WARNING |
| 04 | Price Mismatch | ⚠️ MISMATCH | PRICE_MISMATCH | WARNING |
| 05 | No Match SKU | 🚫 BLOCKED | NO_MATCH | CRITICAL |
| 06 | Invalid PO | 🚫 BLOCKED | INVALID_PO | CRITICAL |
| 07 | Currency Mismatch | 🚫 BLOCKED | CURRENCY_MISMATCH | CRITICAL |
| 08 | Duplicate Billing | 🚫 BLOCKED | DUPLICATE_BILLING | CRITICAL |
| 09 | Mixed Discrepancies | ⚠️ PARTIAL_MATCH | PRICE_MISMATCH + NO_MATCH | WARNING + CRITICAL |
| 10 | Bulk Within Tolerance | ✅ MATCHED | TOLERANCE_VARIANCE | INFO |
| 11 | Strict Vendor Price Mismatch | ⚠️ MISMATCH | PRICE_MISMATCH | WARNING |
| 12 | Multiple Lines All Matched | ✅ MATCHED | — | — |
| 13 | Qty Out of Tolerance | ⚠️ MISMATCH | QUANTITY_MISMATCH | WARNING |
| 14 | Partial Match | ⚠️ PARTIAL_MATCH | PRICE_MISMATCH | WARNING |
| 15 | Single Line Matched | ✅ MATCHED | — | — |

> Run `python scripts/seed_data.py` before uploading demo invoices.

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

### Agent Pipeline (LangGraph)

Three nodes wired into a `StateGraph` sharing a `ReconState` TypedDict:

| Node | Role |
|------|------|
| `extractor` | Calls GPT-4o to extract structured invoice fields; validates with Pydantic; scores confidence |
| `matcher` | Matches invoice lines to open PO lines by `product_code`; applies price/qty tolerances; queries RAG for rule context |
| `exception_handler` | Classifies discrepancies as CRITICAL / WARNING / INFO; sets auto-action (BLOCKED / NEEDS_REVIEW / AUTO_APPROVED); persists to SQLite |

### RAG on Business Rules

- Markdown rule files in `rules/` directory (`reconciliation_rules.md`, `vendor_policies.md`, `rag_training_docs.md`)
- Indexed with Azure OpenAI `text-embedding-ada-002` into a **FAISS** local vector index
- Retrieved at match-time to provide context-aware rule guidance

### Reconciliation Rules Summary

| Rule | Name | Description |
|------|------|-------------|
| 1 | QTY_TOLERANCE_STANDARD | ±5% qty variance allowed; ±10% for bulk `-BULK` SKUs |
| 2 | PRICE_TOLERANCE_STANDARD | ±2% price variance; ±5% when qty matches exactly |
| 3 | PRODUCT_CODE_EXACT_MATCH | Case-insensitive exact product code match required |
| 4 | NO_MATCH_BLOCK | Unmatched product code → CRITICAL exception, DB update blocked |
| 5 | CURRENCY_CONSISTENCY | Invoice currency must match PO currency |
| 6 | CONFIDENCE_GUARDRAIL | Confidence < 0.8 → NEEDS_HUMAN_REVIEW, no DB update |
| 7 | AUTO_APPROVE_WITHIN_TOLERANCE | All lines matched/within tolerance + confidence ≥ 0.8 → auto-approve |
| 8 | PARTIAL_MATCH_REVIEW | Mixed match → PARTIAL_MATCH status, WARNING exceptions raised |

### Observability

- Every pipeline run logs step-by-step messages to the `pipeline_logs` SQLite table
- Streamlit log viewer with `run_id` filtering
- `metrics_runs` table tracks mismatch rate, extraction confidence, and latency per run
- Dashboard charts: mismatch rate over time, confidence over time

### Database Tables

| Table | Description |
|-------|-------------|
| `orders` | Purchase Order headers |
| `order_lines` | Individual PO line items |
| `invoices` | Uploaded invoice headers |
| `invoice_lines` | Extracted invoice line items |
| `reconciliations` | Reconciliation run records |
| `reconciliation_lines` | Line-by-line match results |
| `exceptions` | All raised exceptions with severity & auto-action |
| `invoice_templates` | Template hash fingerprints for drift detection |
| `pipeline_logs` | Step-by-step pipeline execution logs |
| `metrics_runs` | Per-run observability metrics |

---

## License

MIT