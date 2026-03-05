# tests/test_match.py
# Integration tests for the Matcher agent (core/services.py)
# Uses REAL DB + REAL Azure OpenAI RAG - requires .env to be configured.
#
# Run with:
#   pytest tests/test_match.py -v

import pytest
import sqlite3
import importlib
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_env(tmp_path, monkeypatch):
    """
    Setup a real isolated SQLite DB and real rule files for RAG.
    """
    # 1. Isolated DB
    db_path = str(tmp_path / "test_match.db")
    import core.config as cfg
    monkeypatch.setattr(cfg, "SQLITE_DB_PATH", db_path)
    from core.db import init_db
    init_db()

    # 2. Isolated RAG Rules
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "match_rules.md").write_text(
        """# Matching Rules
- If price differs by > 5%, it is a PRICE_MISMATCH.
- If qty differs by > 5%, it is a QUANTITY_MISMATCH.
- If product code is not in PO, it is NO_MATCH and is CRITICAL.
""",
        encoding="utf-8"
    )
    monkeypatch.setattr(cfg, "RULES_DIR", str(rules_dir))
    monkeypatch.setattr(cfg, "RAG_PERSIST_DIR", str(tmp_path / "rag_index"))

    # Reload rag module to pick up new paths
    import core.rules_rag as rag
    importlib.reload(rag)

    yield {"db": db_path, "rules": rules_dir}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def seed_test_data(db_path):
    """Seeds a real PO and invoice into the test DB."""
    conn = sqlite3.connect(db_path)
    # Insert Vendor
    conn.execute("INSERT INTO vendors (id, name) VALUES ('VEND-1', 'Test Vendor')")
    # Insert Order
    conn.execute("INSERT INTO orders (id, vendor_id, status) VALUES ('PO-1', 'VEND-1', 'OPEN')")
    # Insert Order Lines (PROD-A: 100 qty @ $10)
    conn.execute(
        "INSERT INTO order_lines (order_id, product_code, description, ordered_qty, unit_price) "
        "VALUES ('PO-1', 'PROD-A', 'Item A', 100, 10.00)"
    )
    # Insert Invoice (structural record)
    conn.execute(
        "INSERT INTO invoices (vendor_id, vendor_name, status) VALUES ('VEND-1', 'Test Vendor', 'MATCHING')"
    )
    invoice_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return invoice_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_run_matcher_perfect_match(test_env):
    """Should return MATCHED status when qty and price are identical."""
    from core.services import run_matcher
    from core import repositories as repo

    invoice_id = seed_test_data(test_env["db"])

    # Insert Invoice Line (Perfect match)
    repo.insert_invoice_lines(invoice_id, [{
        "line_number": 1,
        "product_code": "PROD-A",
        "quantity": 100,
        "unit_price": 10.00
    }])

    extracted_data = {"vendor_id": "VEND-1", "po_number": "PO-1"}
    recon_id, discrepancies = run_matcher(invoice_id, extracted_data)

    assert len(discrepancies) == 0, "Expected 0 discrepancies for perfect match"

    # Verify DB status
    conn = sqlite3.connect(test_env["db"])
    status = conn.execute("SELECT status FROM reconciliations WHERE id = ?", (recon_id,)).fetchone()[0]
    conn.close()
    assert status == "MATCHED"


def test_run_matcher_price_mismatch_calls_rag(test_env):
    """
    Should detect price mismatch (>5%) and call RAG for rules.
    HITS AZURE OPENAI API for RAG query.
    """
    from core.services import run_matcher
    from core import repositories as repo

    invoice_id = seed_test_data(test_env["db"])

    # Insert Invoice Line ($12 vs $10 PO price = 20% diff > 5% tolerance)
    repo.insert_invoice_lines(invoice_id, [{
        "line_number": 1,
        "product_code": "PROD-A",
        "quantity": 100,
        "unit_price": 12.00
    }])

    extracted_data = {"vendor_id": "VEND-1", "po_number": "PO-1"}
    recon_id, discrepancies = run_matcher(invoice_id, extracted_data)

    assert len(discrepancies) == 1
    d = discrepancies[0]
    assert d["type"] == "PRICE_MISMATCH"
    assert d["price_diff"] == 2.0
    # Rule should be retrieved from RAG (the real rule file we wrote in fixture)
    assert "PRICE_MISMATCH" in d["rule"] or "5%" in d["rule"]


def test_run_matcher_no_match_critical(test_env):
    """
    Should detect product not in PO and flag as NO_MATCH.
    HITS AZURE OPENAI API for RAG query.
    """
    from core.services import run_matcher
    from core import repositories as repo

    invoice_id = seed_test_data(test_env["db"])

    # Product PROD-B is NOT in the seeded PO (which only has PROD-A)
    repo.insert_invoice_lines(invoice_id, [{
        "line_number": 1,
        "product_code": "PROD-B",
        "quantity": 10,
        "unit_price": 50.00
    }])

    extracted_data = {"vendor_id": "VEND-1", "po_number": "PO-1"}
    recon_id, discrepancies = run_matcher(invoice_id, extracted_data)

    assert len(discrepancies) == 1
    assert discrepancies[0]["type"] == "NO_MATCH"
    assert "CRITICAL" in discrepancies[0]["rule"] or "BLOCKED" in discrepancies[0]["rule"]


def test_run_matcher_within_tolerance(test_env):
    """Should return WITHIN_TOLERANCE when diff is exactly 5% (boundary)."""
    from core.services import run_matcher
    from core import repositories as repo

    invoice_id = seed_test_data(test_env["db"])

    # PO Price is $10.00. 5% tolerance = $0.50. Invoice at $10.50 is WITHIN.
    repo.insert_invoice_lines(invoice_id, [{
        "line_number": 1,
        "product_code": "PROD-A",
        "quantity": 100,
        "unit_price": 10.50
    }])

    extracted_data = {"vendor_id": "VEND-1", "po_number": "PO-1"}
    recon_id, _ = run_matcher(invoice_id, extracted_data)

    conn = sqlite3.connect(test_env["db"])
    line_status = conn.execute(
        "SELECT status FROM reconciliation_lines WHERE reconciliation_id = ?", (recon_id,)
    ).fetchone()[0]
    conn.close()

    assert line_status == "WITHIN_TOLERANCE"
