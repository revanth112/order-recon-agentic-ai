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
  from datetime import datetime, timezone
  importlib.reload(repo)
  inv_id = repo.insert_invoice('{}', 'hash_ex', 'V1', 'Vendor')
  # Exceptions require a reconciliation FK, so create one first
  recon_id = repo.create_reconciliation(
      inv_id, 'PO-001', datetime.now(timezone.utc).isoformat()
  )
  repo.insert_exception(
      recon_id=recon_id,
      exc_type='PRICE_MISMATCH',
      severity='WARNING',
      description='Price differs by 5%',
      auto_action='NEEDS_REVIEW',
  )
  exceptions = repo.get_unresolved_exceptions()
  assert len(exceptions) >= 1
  assert exceptions[0]['type'] == 'PRICE_MISMATCH'
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


def test_get_all_orders_empty(tmp_db):
    """get_all_orders returns empty list when no orders exist."""
    import core.repositories as repo
    import importlib
    importlib.reload(repo)
    orders = repo.get_all_orders()
    assert isinstance(orders, list)
    assert len(orders) == 0


def test_get_order_by_id_returns_none(tmp_db):
    """get_order_by_id returns None for nonexistent ID."""
    import core.repositories as repo
    import importlib
    importlib.reload(repo)
    assert repo.get_order_by_id(999) is None


def test_get_order_lines_empty(tmp_db):
    """get_order_lines returns empty list for nonexistent order."""
    import core.repositories as repo
    import importlib
    importlib.reload(repo)
    assert repo.get_order_lines(999) == []


def test_get_all_reconciliations(tmp_db):
    """get_all_reconciliations returns list including created reconciliation."""
    import core.repositories as repo
    import importlib
    from datetime import datetime, timezone
    importlib.reload(repo)
    inv_id = repo.insert_invoice('{}', 'hash', 'V1', 'Vendor')
    recon_id = repo.create_reconciliation(
        inv_id, 'PO-100', datetime.now(timezone.utc).isoformat()
    )
    recons = repo.get_all_reconciliations()
    assert isinstance(recons, list)
    assert len(recons) >= 1
    assert recons[0]['id'] == recon_id


def test_get_reconciliation_by_id(tmp_db):
    """get_reconciliation_by_id returns the correct reconciliation."""
    import core.repositories as repo
    import importlib
    from datetime import datetime, timezone
    importlib.reload(repo)
    inv_id = repo.insert_invoice('{}', 'hash', 'V1', 'Vendor')
    recon_id = repo.create_reconciliation(
        inv_id, 'PO-200', datetime.now(timezone.utc).isoformat()
    )
    recon = repo.get_reconciliation_by_id(recon_id)
    assert recon is not None
    assert recon['po_number'] == 'PO-200'
    assert repo.get_reconciliation_by_id(999) is None


def test_get_reconciliations_for_invoice(tmp_db):
    """get_reconciliations_for_invoice returns reconciliations linked to an invoice."""
    import core.repositories as repo
    import importlib
    from datetime import datetime, timezone
    importlib.reload(repo)
    inv_id = repo.insert_invoice('{}', 'hash', 'V1', 'Vendor')
    recon_id = repo.create_reconciliation(
        inv_id, 'PO-300', datetime.now(timezone.utc).isoformat()
    )
    recons = repo.get_reconciliations_for_invoice(inv_id)
    assert len(recons) == 1
    assert recons[0]['id'] == recon_id
    assert repo.get_reconciliations_for_invoice(999) == []


def test_get_all_exceptions(tmp_db):
    """get_all_exceptions returns both resolved and unresolved exceptions."""
    import core.repositories as repo
    import importlib
    from datetime import datetime, timezone
    importlib.reload(repo)
    inv_id = repo.insert_invoice('{}', 'hash', 'V1', 'Vendor')
    recon_id = repo.create_reconciliation(
        inv_id, 'PO-400', datetime.now(timezone.utc).isoformat()
    )
    repo.insert_exception(recon_id, 'NO_MATCH', 'CRITICAL', 'desc1', 'BLOCKED')
    repo.insert_exception(recon_id, 'PRICE_MISMATCH', 'WARNING', 'desc2', 'NEEDS_REVIEW')
    # Resolve one
    exceptions = repo.get_all_exceptions()
    assert len(exceptions) == 2
    repo.resolve_exception(exceptions[0]['id'], 'tester', datetime.now(timezone.utc).isoformat())
    all_exc = repo.get_all_exceptions()
    assert len(all_exc) == 2  # still 2
    unresolved = repo.get_unresolved_exceptions()
    assert len(unresolved) == 1  # only 1 unresolved


def test_get_exceptions_for_reconciliation(tmp_db):
    """get_exceptions_for_reconciliation returns exceptions for a specific recon."""
    import core.repositories as repo
    import importlib
    from datetime import datetime, timezone
    importlib.reload(repo)
    inv_id = repo.insert_invoice('{}', 'hash', 'V1', 'Vendor')
    recon_id = repo.create_reconciliation(
        inv_id, 'PO-500', datetime.now(timezone.utc).isoformat()
    )
    repo.insert_exception(recon_id, 'NO_MATCH', 'CRITICAL', 'desc', 'BLOCKED')
    exceptions = repo.get_exceptions_for_reconciliation(recon_id)
    assert len(exceptions) == 1
    assert exceptions[0]['type'] == 'NO_MATCH'
    assert repo.get_exceptions_for_reconciliation(999) == []


def test_get_all_templates(tmp_db):
    """get_all_templates returns templates after upsert."""
    import core.repositories as repo
    import importlib
    importlib.reload(repo)
    repo.upsert_template('V1', 'hash_a')
    repo.upsert_template('V2', 'hash_b')
    templates = repo.get_all_templates()
    assert isinstance(templates, list)
    assert len(templates) >= 2
