# tests/test_extract.py
# Integration tests for the Extractor agent (core/services.py)
# Uses REAL Azure OpenAI API - requires .env to be configured.
#
# Run with:
#   pytest tests/test_extract.py -v
#
# Test coverage:
#   1. compute_template_hash()     - same structure = same hash (pure logic)
#   2. compute_template_hash()     - different structure = different hash
#   3. start_invoice_pipeline()    - inserts invoice + template into real DB
#   4. run_extractor()             - calls Azure OpenAI, returns extracted dict
#   5. run_extractor()             - extracted invoice_number matches input
#   6. run_extractor()             - extracted line_items are non-empty
#   7. run_extractor()             - confidence score is between 0 and 1
#   8. run_extractor()             - handles multi-line invoice correctly

import json
import sqlite3
import tempfile
import pytest
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # Load .env so Azure credentials are available


# ---------------------------------------------------------------------------
# Sample invoice data
# ---------------------------------------------------------------------------

SAMPLE_INVOICE = {
    "invoice_number": "INV-TEST-001",
    "vendor_id": "VEND-001",
    "vendor_name": "ABC Supplies",
    "invoice_date": "2026-03-01",
    "po_number": "PO-001",
    "currency": "USD",
    "line_items": [
        {
            "line_number": 1,
            "product_code": "PROD-123",
            "description": "Industrial Bolts M10",
            "quantity": 100,
            "unit_price": 10.50,
            "total": 1050.00,
        }
    ],
}

MULTI_LINE_INVOICE = {
    "invoice_number": "INV-TEST-002",
    "vendor_id": "VEND-002",
    "vendor_name": "Global Tech Corp",
    "invoice_date": "2026-03-05",
    "po_number": "PO-002",
    "currency": "USD",
    "line_items": [
        {
            "line_number": 1,
            "product_code": "PROD-A01",
            "description": "Laptop Stand",
            "quantity": 50,
            "unit_price": 25.00,
            "total": 1250.00,
        },
        {
            "line_number": 2,
            "product_code": "PROD-A02",
            "description": "USB-C Hub",
            "quantity": 30,
            "unit_price": 45.00,
            "total": 1350.00,
        },
        {
            "line_number": 3,
            "product_code": "PROD-A03",
            "description": "HDMI Cable 2m",
            "quantity": 100,
            "unit_price": 8.99,
            "total": 899.00,
        },
    ],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def real_db(tmp_path, monkeypatch):
    """
    Spins up a real SQLite DB in a temp dir and patches the config
    so all repo calls go to this isolated test DB.
    """
    db_path = str(tmp_path / "test_recon.db")
    import core.config as cfg
    monkeypatch.setattr(cfg, "SQLITE_DB_PATH", db_path)

    # Initialise the schema
    from core.db import init_db
    init_db()

    yield db_path


# ---------------------------------------------------------------------------
# 1 & 2 - compute_template_hash() -- pure logic, no API
# ---------------------------------------------------------------------------

def test_compute_template_hash_is_deterministic():
    """Same invoice structure must always produce the same hash."""
    from core.services import compute_template_hash
    h1 = compute_template_hash(SAMPLE_INVOICE)
    h2 = compute_template_hash(SAMPLE_INVOICE)
    assert h1 == h2, "Template hash should be deterministic"


def test_compute_template_hash_changes_on_structure_change():
    """Different invoice structures must produce different hashes."""
    from core.services import compute_template_hash
    modified = {
        "invoice_number": "X",
        "new_field": "extra",
        "line_items": [{"product_code": "X"}],
    }
    h1 = compute_template_hash(SAMPLE_INVOICE)
    h2 = compute_template_hash(modified)
    assert h1 != h2, "Different structures should have different hashes"


# ---------------------------------------------------------------------------
# 3 - start_invoice_pipeline() -- real DB, no API
# ---------------------------------------------------------------------------

def test_start_invoice_pipeline_inserts_into_real_db(real_db):
    """start_invoice_pipeline should insert invoice and return a valid int ID."""
    from core.services import start_invoice_pipeline, compute_template_hash

    raw_json = json.dumps(SAMPLE_INVOICE)
    template_hash = compute_template_hash(SAMPLE_INVOICE)

    invoice_id = start_invoice_pipeline(
        raw_json,
        vendor_id="VEND-001",
        vendor_name="ABC Supplies",
        template_hash=template_hash,
    )

    assert isinstance(invoice_id, int), "Invoice ID must be an integer"
    assert invoice_id > 0, "Invoice ID must be positive"

    # Verify the record exists in the DB
    conn = sqlite3.connect(real_db)
    row = conn.execute(
        "SELECT id, vendor_id FROM invoices WHERE id = ?", (invoice_id,)
    ).fetchone()
    conn.close()
    assert row is not None, "Invoice must exist in DB"
    assert row[1] == "VEND-001"


# ---------------------------------------------------------------------------
# 4, 5, 6, 7 - run_extractor() -- HITS AZURE OPENAI API
# ---------------------------------------------------------------------------

def test_run_extractor_returns_extracted_dict(real_db):
    """
    Real integration test: run_extractor sends the invoice JSON to
    Azure OpenAI and returns a structured extraction dict.
    """
    from core.services import start_invoice_pipeline, compute_template_hash, run_extractor

    raw_json = json.dumps(SAMPLE_INVOICE)
    template_hash = compute_template_hash(SAMPLE_INVOICE)
    invoice_id = start_invoice_pipeline(
        raw_json, "VEND-001", "ABC Supplies", template_hash
    )

    extracted, confidence = run_extractor(invoice_id, SAMPLE_INVOICE)

    assert isinstance(extracted, dict), "Extracted result must be a dict"
    assert isinstance(confidence, float), "Confidence must be a float"


def test_run_extractor_invoice_number_matches(real_db):
    """
    Azure OpenAI must correctly extract the invoice_number from the JSON.
    """
    from core.services import start_invoice_pipeline, compute_template_hash, run_extractor

    raw_json = json.dumps(SAMPLE_INVOICE)
    template_hash = compute_template_hash(SAMPLE_INVOICE)
    invoice_id = start_invoice_pipeline(
        raw_json, "VEND-001", "ABC Supplies", template_hash
    )

    extracted, _ = run_extractor(invoice_id, SAMPLE_INVOICE)

    assert extracted.get("invoice_number") == "INV-TEST-001", (
        f"Expected invoice_number=INV-TEST-001, got: {extracted.get('invoice_number')}"
    )


def test_run_extractor_line_items_non_empty(real_db):
    """
    Extracted line_items must not be empty and must contain the product code.
    """
    from core.services import start_invoice_pipeline, compute_template_hash, run_extractor

    raw_json = json.dumps(SAMPLE_INVOICE)
    template_hash = compute_template_hash(SAMPLE_INVOICE)
    invoice_id = start_invoice_pipeline(
        raw_json, "VEND-001", "ABC Supplies", template_hash
    )

    extracted, _ = run_extractor(invoice_id, SAMPLE_INVOICE)

    line_items = extracted.get("line_items", [])
    assert len(line_items) > 0, "Extracted line_items must not be empty"

    # At least one line item should have the correct product code
    product_codes = [li.get("product_code") for li in line_items]
    assert "PROD-123" in product_codes, (
        f"Expected PROD-123 in product codes, got: {product_codes}"
    )


def test_run_extractor_confidence_is_valid(real_db):
    """
    Confidence score must be between 0.0 and 1.0 inclusive.
    """
    from core.services import start_invoice_pipeline, compute_template_hash, run_extractor

    raw_json = json.dumps(SAMPLE_INVOICE)
    template_hash = compute_template_hash(SAMPLE_INVOICE)
    invoice_id = start_invoice_pipeline(
        raw_json, "VEND-001", "ABC Supplies", template_hash
    )

    _, confidence = run_extractor(invoice_id, SAMPLE_INVOICE)

    assert 0.0 <= confidence <= 1.0, (
        f"Confidence must be in [0, 1], got: {confidence}"
    )


# ---------------------------------------------------------------------------
# 8 - run_extractor() multi-line invoice -- HITS AZURE OPENAI API
# ---------------------------------------------------------------------------

def test_run_extractor_handles_multi_line_invoice(real_db):
    """
    Azure OpenAI must correctly extract all 3 line items from a
    multi-line invoice without dropping any.
    """
    from core.services import start_invoice_pipeline, compute_template_hash, run_extractor

    raw_json = json.dumps(MULTI_LINE_INVOICE)
    template_hash = compute_template_hash(MULTI_LINE_INVOICE)
    invoice_id = start_invoice_pipeline(
        raw_json, "VEND-002", "Global Tech Corp", template_hash
    )

    extracted, confidence = run_extractor(invoice_id, MULTI_LINE_INVOICE)

    assert extracted.get("invoice_number") == "INV-TEST-002"
    assert extracted.get("vendor_id") == "VEND-002"

    line_items = extracted.get("line_items", [])
    assert len(line_items) == 3, (
        f"Expected 3 line items, got: {len(line_items)}"
    )

    product_codes = {li.get("product_code") for li in line_items}
    assert product_codes == {"PROD-A01", "PROD-A02", "PROD-A03"}, (
        f"Unexpected product codes: {product_codes}"
    )
    assert confidence > 0.5, (
        f"Expected high confidence for well-formed invoice, got: {confidence}"
    )
