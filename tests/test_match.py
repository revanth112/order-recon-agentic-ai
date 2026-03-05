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
    # Reload core.db so its module-level SQLITE_DB_PATH picks up the new path
    import core.db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    # Reload repositories so it uses the reloaded db module
    import core.repositories as repo_module
    importlib.reload(repo_module)

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
    # Insert Order (no vendors table; vendor_id is just a text field on orders)
    conn.execute(
        "INSERT INTO orders (po_number, vendor_id, vendor_name, status) "
        "VALUES ('PO-1', 'VEND-1', 'Test Vendor', 'OPEN')"
    )
    order_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    # Insert Order Lines (PROD-A: 100 qty @ $10)
    conn.execute(
        "INSERT INTO order_lines (order_id, line_number, product_code, description, ordered_qty, unit_price) "
        "VALUES (?, 1, 'PROD-A', 'Item A', 100, 10.00)",
        (order_id,),
    )
    # Insert Invoice (structural record)
    conn.execute(
        "INSERT INTO invoices (vendor_id, vendor_name, raw_json, status) "
        "VALUES ('VEND-1', 'Test Vendor', '{}', 'MATCHING')"
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
    status = conn.execute("SELECT overall_status FROM reconciliations WHERE id = ?", (recon_id,)).fetchone()[0]
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
        "SELECT match_status FROM reconciliation_lines WHERE reconciliation_id = ?", (recon_id,)
    ).fetchone()[0]
    conn.close()

    assert line_status == "WITHIN_TOLERANCE"


def test_run_matcher_within_tolerance_creates_discrepancy(test_env):
    """WITHIN_TOLERANCE should produce a TOLERANCE_VARIANCE discrepancy for audit trail."""
    from core.services import run_matcher
    from core import repositories as repo

    invoice_id = seed_test_data(test_env["db"])

    repo.insert_invoice_lines(invoice_id, [{
        "line_number": 1,
        "product_code": "PROD-A",
        "quantity": 100,
        "unit_price": 10.50  # 5% diff — within default tolerance
    }])

    extracted_data = {"vendor_id": "VEND-1", "po_number": "PO-1"}
    recon_id, discrepancies = run_matcher(invoice_id, extracted_data)

    assert len(discrepancies) == 1
    assert discrepancies[0]["type"] == "TOLERANCE_VARIANCE"

    # Overall status should still be MATCHED (TOLERANCE_VARIANCE not a hard discrepancy)
    conn = sqlite3.connect(test_env["db"])
    status = conn.execute(
        "SELECT overall_status FROM reconciliations WHERE id = ?", (recon_id,)
    ).fetchone()[0]
    conn.close()
    assert status == "MATCHED"


def test_run_matcher_invalid_po(test_env):
    """Should return INVALID_PO status when no matching open order exists for the PO+vendor."""
    from core.services import run_matcher
    from core import repositories as repo

    invoice_id = seed_test_data(test_env["db"])

    repo.insert_invoice_lines(invoice_id, [{
        "line_number": 1,
        "product_code": "PROD-A",
        "quantity": 100,
        "unit_price": 10.00
    }])

    # Use a PO number that does NOT exist in the DB
    extracted_data = {"vendor_id": "VEND-1", "po_number": "PO-NONEXISTENT"}
    recon_id, discrepancies = run_matcher(invoice_id, extracted_data)

    assert len(discrepancies) == 1
    assert discrepancies[0]["type"] == "INVALID_PO"

    conn = sqlite3.connect(test_env["db"])
    status = conn.execute(
        "SELECT overall_status FROM reconciliations WHERE id = ?", (recon_id,)
    ).fetchone()[0]
    conn.close()
    assert status == "INVALID_PO"


def test_run_matcher_invalid_po_wrong_vendor(test_env):
    """Should return INVALID_PO when PO exists but vendor_id does not match."""
    from core.services import run_matcher
    from core import repositories as repo

    invoice_id = seed_test_data(test_env["db"])

    repo.insert_invoice_lines(invoice_id, [{
        "line_number": 1,
        "product_code": "PROD-A",
        "quantity": 100,
        "unit_price": 10.00
    }])

    # PO-1 exists but belongs to VEND-1, not VEND-2
    extracted_data = {"vendor_id": "VEND-2", "po_number": "PO-1"}
    recon_id, discrepancies = run_matcher(invoice_id, extracted_data)

    assert len(discrepancies) == 1
    assert discrepancies[0]["type"] == "INVALID_PO"


def test_run_matcher_duplicate_billing(test_env):
    """Should detect DUPLICATE_BILLING when same order line has already been reconciled."""
    from core.services import run_matcher
    from core import repositories as repo

    # First reconciliation — perfect match for all 100 units
    invoice_id_1 = seed_test_data(test_env["db"])
    repo.insert_invoice_lines(invoice_id_1, [{
        "line_number": 1,
        "product_code": "PROD-A",
        "quantity": 100,
        "unit_price": 10.00
    }])
    recon_id_1, discrepancies_1 = run_matcher(invoice_id_1, {"vendor_id": "VEND-1", "po_number": "PO-1"})
    assert len(discrepancies_1) == 0  # First invoice matched cleanly

    # Create a second invoice for the same vendor/PO/product — this is duplicate billing
    conn = sqlite3.connect(test_env["db"])
    conn.execute(
        "INSERT INTO invoices (vendor_id, vendor_name, raw_json, status) "
        "VALUES ('VEND-1', 'Test Vendor', '{}', 'MATCHING')"
    )
    invoice_id_2 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()

    repo.insert_invoice_lines(invoice_id_2, [{
        "line_number": 1,
        "product_code": "PROD-A",
        "quantity": 50,   # Trying to bill again for 50 of the 100 already reconciled
        "unit_price": 10.00
    }])

    recon_id_2, discrepancies_2 = run_matcher(invoice_id_2, {"vendor_id": "VEND-1", "po_number": "PO-1"})

    assert len(discrepancies_2) == 1
    assert discrepancies_2[0]["type"] == "DUPLICATE_BILLING"
    assert discrepancies_2[0]["already_reconciled_qty"] == 100.0


def test_run_matcher_vendor_specific_tolerance(test_env):
    """Should use per-vendor tolerance from VENDOR_TOLERANCES, not global defaults."""
    from core.services import run_matcher
    from core import repositories as repo

    # Insert an order for V-003 (strict: 1% price, 3% qty)
    conn = sqlite3.connect(test_env["db"])
    conn.execute(
        "INSERT INTO orders (po_number, vendor_id, vendor_name, status) "
        "VALUES ('PO-V003', 'V-003', 'FastParts', 'OPEN')"
    )
    order_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO order_lines (order_id, line_number, product_code, description, ordered_qty, unit_price) "
        "VALUES (?, 1, 'PART-X', 'Part X', 100, 10.00)",
        (order_id,),
    )
    conn.execute(
        "INSERT INTO invoices (vendor_id, vendor_name, raw_json, status) "
        "VALUES ('V-003', 'FastParts', '{}', 'MATCHING')"
    )
    invoice_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()

    # 3% price diff — within default 5% but OVER V-003's strict 1% limit
    repo.insert_invoice_lines(invoice_id, [{
        "line_number": 1,
        "product_code": "PART-X",
        "quantity": 100,
        "unit_price": 10.30  # 3% above $10.00 — exceeds V-003's 1% price tolerance
    }])

    recon_id, discrepancies = run_matcher(invoice_id, {"vendor_id": "V-003", "po_number": "PO-V003"})

    # Should be PRICE_MISMATCH because V-003 only allows 1% price tolerance
    assert len(discrepancies) == 1
    assert discrepancies[0]["type"] == "PRICE_MISMATCH"

    conn = sqlite3.connect(test_env["db"])
    status = conn.execute(
        "SELECT overall_status FROM reconciliations WHERE id = ?", (recon_id,)
    ).fetchone()[0]
    conn.close()
    assert status == "MISMATCH"


def test_handle_exceptions_tolerance_variance_auto_approved(test_env):
    """TOLERANCE_VARIANCE discrepancies should produce INFO/AUTO_APPROVED exceptions."""
    import sqlite3
    from core.services import handle_exceptions
    from core import repositories as repo
    from datetime import datetime, timezone

    conn = sqlite3.connect(test_env["db"])
    conn.execute(
        "INSERT INTO invoices (vendor_id, vendor_name, raw_json, status) "
        "VALUES ('V-001', 'Acme', '{}', 'MATCHING')"
    )
    invoice_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()

    recon_id = repo.create_reconciliation(
        invoice_id, "PO-TEST", datetime.now(timezone.utc).isoformat()
    )

    discrepancies = [{
        "type": "TOLERANCE_VARIANCE",
        "product_code": "SKU-1",
        "qty_diff": 1,
        "price_diff": 0.05,
        "rule": "Within vendor tolerance",
        "invoice_line_id": 1,
        "order_line_id": 1,
    }]
    handle_exceptions(recon_id, discrepancies)

    exceptions = repo.get_exceptions_for_reconciliation(recon_id)
    assert len(exceptions) == 1
    assert exceptions[0]["severity"] == "INFO"
    assert exceptions[0]["auto_action"] == "AUTO_APPROVED"


def test_handle_exceptions_invalid_po_blocked(test_env):
    """INVALID_PO discrepancies should produce CRITICAL/BLOCKED exceptions."""
    import sqlite3
    from core.services import handle_exceptions
    from core import repositories as repo
    from datetime import datetime, timezone

    conn = sqlite3.connect(test_env["db"])
    conn.execute(
        "INSERT INTO invoices (vendor_id, vendor_name, raw_json, status) "
        "VALUES ('V-001', 'Acme', '{}', 'MATCHING')"
    )
    invoice_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()

    recon_id = repo.create_reconciliation(
        invoice_id, "PO-BAD", datetime.now(timezone.utc).isoformat()
    )

    discrepancies = [{
        "type": "INVALID_PO",
        "product_code": None,
        "po_number": "PO-BAD",
        "rule": "No matching rule found. Flag for manual review.",
    }]
    handle_exceptions(recon_id, discrepancies)

    exceptions = repo.get_exceptions_for_reconciliation(recon_id)
    assert len(exceptions) == 1
    assert exceptions[0]["severity"] == "CRITICAL"
    assert exceptions[0]["auto_action"] == "BLOCKED"
