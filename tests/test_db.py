# tests/test_db.py - Integration tests for the SQLite repository layer
import os
import pytest
import tempfile


@pytest.fixture
def tmp_db(monkeypatch):
    """Create a temporary SQLite DB for each test."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    monkeypatch.setenv('SQLITE_DB_PATH', db_path)
    # Re-import config with new env var
    import importlib
    import core.config as cfg
    importlib.reload(cfg)
    import core.db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    yield db_path
    os.unlink(db_path)


def test_insert_and_get_invoice(tmp_db):
    """Inserting an invoice should return a valid ID and be retrievable."""
    import core.repositories as repo
    import importlib
    importlib.reload(repo)
    inv_id = repo.insert_invoice(
        raw_json='{"test": true}',
        template_hash='abc123',
        vendor_id='VEND-001',
        vendor_name='Test Vendor',
        invoice_number='INV-TEST',
    )
    assert inv_id is not None
    assert isinstance(inv_id, int)
    assert inv_id > 0

    inv = repo.get_invoice_by_id(inv_id)
    assert inv is not None
    assert inv['vendor_id'] == 'VEND-001'
    assert inv['status'] == 'UPLOADED'



def test_get_all_invoices(tmp_db):
  """Getting all invoices should return a list."""
  import core.repositories as repo
  import importlib
  importlib.reload(repo)
  repo.insert_invoice('{}', 'hash1', 'V1', 'Vendor A')
  repo.insert_invoice('{}', 'hash2', 'V2', 'Vendor B')
  invoices = repo.get_all_invoices()
  assert isinstance(invoices, list)
  assert len(invoices) >= 2


def test_insert_exception(tmp_db):
  """Inserting an exception record should succeed."""
  import core.repositories as repo
  import importlib
  importlib.reload(repo)
  inv_id = repo.insert_invoice('{}', 'hash_ex', 'V1', 'Vendor')
  repo.insert_exception(
    invoice_id=inv_id,
    po_number='PO-001',
    exception_type='PRICE_MISMATCH',
    field_name='unit_price',
    invoice_value=100.0,
    po_value=95.0,
    severity='HIGH',
    notes='Price differs by 5'
  )
  exceptions = repo.get_exceptions_for_invoice(inv_id)
  assert len(exceptions) >= 1
  assert exceptions[0]['exception_type'] == 'PRICE_MISMATCH'
def test_update_invoice_status(tmp_db):
    """Updating invoice status should persist correctly."""
    import core.repositories as repo
    import importlib
    importlib.reload(repo)
    inv_id = repo.insert_invoice('{}', 'hash', 'V1', 'Vendor')
    repo.update_invoice_status(inv_id, 'EXTRACTING', extraction_confidence=0.95)
    inv = repo.get_invoice_by_id(inv_id)
    assert inv['status'] == 'EXTRACTING'
    assert abs(inv['extraction_confidence'] - 0.95) < 0.001


# TODO: Add tests for reconciliation, exceptions, and template drift
