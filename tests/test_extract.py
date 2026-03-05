# tests/test_extract.py - Unit tests for the Extractor agent
import pytest
from unittest.mock import MagicMock, patch


# --- Sample invoice JSON for testing ---
SAMPLE_INVOICE = {
    "invoice_number": "INV-TEST-001",
    "vendor_id": "VEND-001",
    "vendor_name": "ABC Supplies",
    "invoice_date": "2026-03-01",
    "po_number": "PO-001",
    "currency": "USD",
    "line_items": [
        {"line_number": 1, "product_code": "PROD-123", "quantity": 100, "unit_price": 10.50},
    ],
}


def test_compute_template_hash_is_deterministic():
    """Same invoice structure should always produce the same hash."""
    from core.services import compute_template_hash
    h1 = compute_template_hash(SAMPLE_INVOICE)
    h2 = compute_template_hash(SAMPLE_INVOICE)
    assert h1 == h2, "Template hash should be deterministic"


def test_compute_template_hash_changes_on_structure_change():
    """Different invoice structures should produce different hashes."""
    from core.services import compute_template_hash
    modified = {"invoice_number": "X", "new_field": "extra", "line_items": [{"product_code": "X"}]}
    h1 = compute_template_hash(SAMPLE_INVOICE)
    h2 = compute_template_hash(modified)
    assert h1 != h2, "Different structures should have different hashes"


@patch("core.services.repo")
def test_start_invoice_pipeline_returns_invoice_id(mock_repo):
    """start_invoice_pipeline should return a valid invoice_id from the DB."""
    from core.services import start_invoice_pipeline
    mock_repo.insert_invoice.return_value = 42
    mock_repo.upsert_template.return_value = None

    result = start_invoice_pipeline("{}", "VEND-001", "ABC Supplies", "hash123")
    assert result == 42
    mock_repo.insert_invoice.assert_called_once()
    mock_repo.upsert_template.assert_called_once()


# TODO: Add integration test with mocked LLM for run_extractor
