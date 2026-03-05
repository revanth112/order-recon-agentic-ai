# Order Reconciliation Agentic AI

> **Multi-Agent Order Reconciliation System** using LangGraph, GPT-4o, ChromaDB (RAG), SQLite and Streamlit

---

## Problem Statement

Finance and operations teams reconcile invoices, Purchase Orders (POs), and delivery records **manually** — a process that is slow, error-prone, and causes delays in month-end closing.

## Solution

A **multi-agent AI system** that:
- Accepts invoice JSON as input
- Extracts structured fields using GPT-4o
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
 [Extractor Agent]  <-- GPT-4o structured extraction + Pydantic validation
       |
       v
 [Matcher Agent]    <-- RAG on business rules (ChromaDB) + tolerance logic
       |
       v
 [Exception Handler Agent]  <-- Severity classification + DB update
       |
       v
 [SQLite Database]  <-- invoices, purchase_orders, exceptions tables
       |
       v
 [Streamlit UI]     <-- Exception reports, metrics dashboard, pipeline runner
```

**Orchestration**: LangGraph `StateGraph` with typed state passing between agents.

---

## Project Structure

```
order-recon-agentic-ai/
├── agents/
│   ├── __init__.py
│   ├── extractor.py        # Extractor Agent - GPT-4o field extraction
│   ├── matcher.py          # Matcher Agent - RAG + tolerance matching
│   ├── exception_handler.py # Exception Handler Agent - severity + DB write
│   └── graph.py            # LangGraph StateGraph orchestration
├── core/
│   ├── __init__.py
│   ├── config.py           # Environment config (OpenAI key, DB path)
│   ├── db.py               # SQLite schema init
│   ├── repositories.py     # CRUD operations for invoices/exceptions
│   ├── services.py         # Pipeline runner, hash utilities
│   └── metrics.py          # Observability: mismatch rates, dashboard stats
├── data/
│   ├── invoice_v1.json     # Sample invoice - clean match
│   └── invoice_v2.json     # Sample invoice - mismatch test case
├── models/
│   └── schemas.py          # Pydantic models: InvoiceData, LineItem, etc.
├── rules/
│   └── vendor_policies.md  # Business rules / reconciliation guidelines
├── streamlit_app/
│   ├── __init__.py
│   └── app.py              # Full Streamlit UI with tabs and metrics
├── tests/
│   ├── __init__.py
│   ├── test_db.py          # Integration tests - SQLite repository layer
│   ├── test_extract.py     # Unit tests - extractor agent logic
│   └── test_match.py       # Unit tests - matcher tolerance logic
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Core Features

| Feature | Details |
|---|---|
| **Structured Extraction** | GPT-4o extracts vendor, PO number, line items from raw invoice JSON |
| **RAG on Business Rules** | ChromaDB vector store over `vendor_policies.md` guides matching decisions |
| **Multi-Agent Pipeline** | Extractor → Matcher → Exception Handler via LangGraph |
| **Match Rules** | Quantity tolerance (±2%), price tolerance (±5%), product code exact match |
| **Auto DB Update** | SQLite updated automatically with invoice status and exceptions |
| **Exception Report UI** | Streamlit dashboard with filterable exception table and metrics |
| **Observability** | Mismatch rate, exception severity breakdown, pipeline run history |

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- OpenAI API key

### Install

```bash
git clone https://github.com/revanth112/order-recon-agentic-ai.git
cd order-recon-agentic-ai
pip install -r requirements.txt
```

### Configure

Create a `.env` file in the root:

```env
OPENAI_API_KEY=sk-your-key-here
SQLITE_DB_PATH=./recon.db
```

### Run the Streamlit App

```bash
streamlit run streamlit_app/app.py
```

### Run Tests

```bash
pytest tests/ -v --cov=. --cov-report=term-missing
```

---

## Agent Details

### 1. Extractor Agent (`agents/extractor.py`)
- Uses GPT-4o with function calling
- Extracts: vendor ID, invoice number, PO number, line items (product code, qty, unit price)
- Validates output against `InvoiceData` Pydantic schema
- Computes SHA-256 hash for deduplication

### 2. Matcher Agent (`agents/matcher.py`)
- Queries ChromaDB for relevant business rules via RAG
- Compares invoice line items against PO records from SQLite
- Applies configurable tolerances (quantity ±2%, price ±5%)
- Outputs: MATCHED, PARTIAL_MATCH, or MISMATCH with field-level diff

### 3. Exception Handler Agent (`agents/exception_handler.py`)
- Classifies exceptions by severity: HIGH / MEDIUM / LOW
- Writes exceptions to SQLite `exceptions` table
- Updates invoice status: MATCHED / EXCEPTION
- Generates a structured exception report dict

### 4. LangGraph Orchestration (`agents/graph.py`)
- `StateGraph` with typed `ReconState`
- Nodes: `extract` → `match` → `handle_exceptions` → `END`
- Full state passed between nodes for traceability

---

## Streamlit UI Tabs

| Tab | Description |
|---|---|
| **Run Pipeline** | Upload invoice JSON and trigger full reconciliation pipeline |
| **Exception Report** | Browse all exceptions with severity filter, export to CSV |
| **Dashboard** | Metrics: total invoices, match rate, exception counts by severity |
| **Invoice History** | Browse all processed invoices and their statuses |

---

## Sample Invoice Format

```json
{
  "invoice_number": "INV-2024-001",
  "vendor_id": "VEND-001",
  "vendor_name": "Tech Supplies Ltd",
  "po_number": "PO-2024-001",
  "invoice_date": "2024-01-15",
  "line_items": [
    {
      "product_code": "LAPTOP-PRO-15",
      "description": "Professional Laptop 15 inch",
      "quantity": 10,
      "unit_price": 1250.00,
      "total_price": 12500.00
    }
  ],
  "subtotal": 12500.00,
  "tax": 1250.00,
  "total_amount": 13750.00,
  "currency": "USD"
}
```

---

## Tech Stack

- **LLM**: OpenAI GPT-4o (via `langchain-openai`)
- **Agent Framework**: LangGraph (`StateGraph`)
- **RAG / Vector DB**: ChromaDB
- **Data Validation**: Pydantic v2
- **Database**: SQLite (built-in)
- **UI**: Streamlit + Plotly
- **Testing**: pytest + pytest-cov
- **Language**: Python 3.10+

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

*Built as a capstone project demonstrating multi-agent AI systems for financial operations automation.*


### 📊 Data Generation & Seeding
To train the RAG system and test the agents with a large volume of realistic data, run:
```bash
python scripts/generate_data.py
```
This will:
1. Create 1000 orders in the `data/order_recon.db`.
2. Generate 1000 corresponding invoice JSON files in `data/invoices/`.
3. Randomly introduce common discrepancies (price, quantity, SKU) for testing.

### 🚀 Getting Started
1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`.
3. Set up your `.env` with `OPENAI_API_KEY`.
4. Run the data generator: `python scripts/generate_data.py`.
5. Start the UI: `streamlit run streamlit_app/main.py`.
