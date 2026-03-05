# tests/test_logging.py
# Validates the pipeline logging system end-to-end.
# Runs against a temp SQLite DB so no real data is touched.
"""
Test coverage:
  1. new_run_id()          - returns a valid UUID4 string
  2. _infer_agent()        - maps bracketed prefixes to agent names
  3. _infer_level()        - maps keywords to severity levels
  4. log_entry()           - single row written correctly
  5. persist_logs()        - bulk list of log strings written correctly
  6. get_logs_for_invoice()- returns correct rows filtered by invoice_id
  7. get_logs_for_run()    - returns rows for a specific run in order
  8. get_all_logs()        - level and agent filters work
  9. get_run_summary()     - counts by level/agent, flags errors/warnings
 10. Validation checklist  - all three agents present in summary
"""

import os
import sqlite3
import tempfile
import uuid
import importlib
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
  """
  Redirect SQLITE_DB_PATH to a fresh temp file for every test.
  Also initialise the schema so pipeline_logs table exists.
  """
  db_path = str(tmp_path / 'test_recon.db')

  # Patch config before importing logger / db
  import core.config as cfg
  monkeypatch.setattr(cfg, 'SQLITE_DB_PATH', db_path)

  # Re-import db and logger so they pick up the new path
  import core.db as db_mod
  import core.logger as log_mod
  importlib.reload(db_mod)
  importlib.reload(log_mod)

  # Create tables (including pipeline_logs)
  db_mod.init_db()

  # Seed a minimal invoice row so FK constraint is satisfied
  conn = sqlite3.connect(db_path)
  conn.execute(
    "INSERT INTO invoices (id, vendor_id, raw_json) VALUES (1, 'V1', '{}')"
  )
  conn.commit()
  conn.close()

  yield db_path


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_log_mod():
  """Always reload to get the patched module."""
  import core.logger as m
  importlib.reload(m)
  return m


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestNewRunId:
  def test_returns_string(self):
    m = _get_log_mod()
    rid = m.new_run_id()
    assert isinstance(rid, str)

  def test_is_valid_uuid4(self):
    m = _get_log_mod()
    rid = m.new_run_id()
    parsed = uuid.UUID(rid, version=4)
    assert str(parsed) == rid

  def test_unique_each_call(self):
    m = _get_log_mod()
    ids = {m.new_run_id() for _ in range(10)}
    assert len(ids) == 10


class TestInferAgent:
  def test_extractor_tag(self):
    m = _get_log_mod()
    assert m._infer_agent('[EXTRACTOR] Starting...') == 'EXTRACTOR'

  def test_matcher_tag(self):
    m = _get_log_mod()
    assert m._infer_agent('[MATCHER] Found 2 discrepancies.') == 'MATCHER'

  def test_exception_handler_tag(self):
    m = _get_log_mod()
    assert m._infer_agent('[EXCEPTION HANDLER] Done.') == 'EXCEPTION_HANDLER'

  def test_unknown_defaults_to_system(self):
    m = _get_log_mod()
    assert m._infer_agent('Some random message') == 'SYSTEM'


class TestInferLevel:
  def test_info_default(self):
    m = _get_log_mod()
    assert m._infer_level('[EXTRACTOR] Starting...') == 'INFO'

  def test_warning_keyword(self):
    m = _get_log_mod()
    assert m._infer_level('[EXTRACTOR] WARNING: Low confidence') == 'WARNING'

  def test_low_confidence_maps_to_warning(self):
    m = _get_log_mod()
    assert m._infer_level('[EXTRACTOR] Low confidence (0.45)') == 'WARNING'

  def test_error_keyword(self):
    m = _get_log_mod()
    assert m._infer_level('[MATCHER] ERROR: connection failed') == 'ERROR'

  def test_failed_keyword(self):
    m = _get_log_mod()
    assert m._infer_level('Pipeline FAILED') == 'ERROR'


# ---------------------------------------------------------------------------
# Integration tests (write + read from tmp SQLite)
# ---------------------------------------------------------------------------

class TestLogEntry:
  def test_single_entry_persisted(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    m.log_entry(invoice_id=1, run_id=rid, message='[EXTRACTOR] Test entry')
    rows = m.get_logs_for_invoice(1)
    assert len(rows) >= 1
    assert any(r['message'] == '[EXTRACTOR] Test entry' for r in rows)

  def test_agent_inferred_correctly(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    m.log_entry(invoice_id=1, run_id=rid, message='[MATCHER] Matched 5 lines')
    rows = m.get_logs_for_invoice(1)
    matcher_rows = [r for r in rows if r['agent'] == 'MATCHER']
    assert len(matcher_rows) >= 1

  def test_level_inferred_as_warning(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    m.log_entry(invoice_id=1, run_id=rid, message='[EXTRACTOR] WARNING: low conf')
    rows = m.get_logs_for_invoice(1)
    warn_rows = [r for r in rows if r['level'] == 'WARNING']
    assert len(warn_rows) >= 1

  def test_override_agent_and_level(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    m.log_entry(invoice_id=1, run_id=rid, message='Custom',
                agent='SYSTEM', level='ERROR')
    rows = m.get_logs_for_invoice(1)
    custom = [r for r in rows if r['message'] == 'Custom']
    assert custom[0]['agent'] == 'SYSTEM'
    assert custom[0]['level'] == 'ERROR'


class TestPersistLogs:
  def test_bulk_persist(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    messages = [
      '[EXTRACTOR] Starting...',
      '[EXTRACTOR] Completed. Confidence=0.92',
      '[MATCHER] Starting order matching...',
      '[MATCHER] Found 1 discrepancies. Latency=120ms',
      '[EXCEPTION HANDLER] Processing exceptions...',
      '[EXCEPTION HANDLER] Done. Pipeline completed.',
    ]
    m.persist_logs(invoice_id=1, run_id=rid, log_entries=messages)
    rows = m.get_logs_for_run(rid)
    assert len(rows) == 6

  def test_order_preserved(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    msgs = [f'Step {i}' for i in range(5)]
    m.persist_logs(invoice_id=1, run_id=rid, log_entries=msgs)
    rows = m.get_logs_for_run(rid)
    assert [r['message'] for r in rows] == msgs


class TestGetAllLogs:
  def test_level_filter_info_only(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    m.log_entry(1, rid, '[EXTRACTOR] Normal step')         # INFO
    m.log_entry(1, rid, '[EXTRACTOR] WARNING: low conf')   # WARNING
    info_rows = m.get_all_logs(level='INFO')
    assert all(r['level'] == 'INFO' for r in info_rows)

  def test_agent_filter(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    m.log_entry(1, rid, '[EXTRACTOR] Done')
    m.log_entry(1, rid, '[MATCHER] Done')
    ext_rows = m.get_all_logs(agent='EXTRACTOR')
    assert all(r['agent'] == 'EXTRACTOR' for r in ext_rows)

  def test_limit_respected(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    for i in range(20):
      m.log_entry(1, rid, f'Log {i}')
    rows = m.get_all_logs(limit=5)
    assert len(rows) <= 5


class TestRunSummary:
  def _seed_full_run(self, m, rid):
    messages = [
      '[EXTRACTOR] Starting...',
      '[EXTRACTOR] Completed. Confidence=0.90',
      '[MATCHER] Starting order matching...',
      '[MATCHER] Found 0 discrepancies. Latency=80ms',
      '[EXCEPTION HANDLER] Processing exceptions...',
      '[EXCEPTION HANDLER] Done. Pipeline completed.',
    ]
    m.persist_logs(invoice_id=1, run_id=rid, log_entries=messages)

  def test_total_count(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    self._seed_full_run(m, rid)
    summary = m.get_run_summary(rid)
    assert summary['total'] == 6

  def test_agents_executed_all_three(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    self._seed_full_run(m, rid)
    summary = m.get_run_summary(rid)
    assert 'EXTRACTOR' in summary['agents_executed']
    assert 'MATCHER' in summary['agents_executed']
    assert 'EXCEPTION_HANDLER' in summary['agents_executed']

  def test_no_errors_in_clean_run(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    self._seed_full_run(m, rid)
    summary = m.get_run_summary(rid)
    assert summary['has_errors'] is False

  def test_error_detected(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    m.log_entry(1, rid, '[MATCHER] ERROR: DB connection failed')
    summary = m.get_run_summary(rid)
    assert summary['has_errors'] is True

  def test_warning_detected(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    m.log_entry(1, rid, '[EXTRACTOR] WARNING: Low confidence (0.45)')
    summary = m.get_run_summary(rid)
    assert summary['has_warnings'] is True

  def test_by_level_counts(self, tmp_db):
    m = _get_log_mod()
    rid = m.new_run_id()
    self._seed_full_run(m, rid)
    m.log_entry(1, rid, '[EXTRACTOR] WARNING: border case')
    summary = m.get_run_summary(rid)
    assert summary['by_level']['INFO'] == 6
    assert summary['by_level']['WARNING'] == 1
    assert summary['by_level']['ERROR'] == 0

  def test_validation_checklist_passes_for_clean_run(self, tmp_db):
    """
    Simulate the exact validation logic from the Streamlit log_viewer.
    For a clean, full pipeline run every check should pass
    (except the 'Low confidence warning' which is optional).
    """
    m = _get_log_mod()
    rid = m.new_run_id()
    self._seed_full_run(m, rid)
    summary = m.get_run_summary(rid)
    agents = summary['agents_executed']
    checks = {
      'Extractor ran':         'EXTRACTOR' in agents,
      'Matcher ran':           'MATCHER' in agents,
      'Exception handler ran': 'EXCEPTION_HANDLER' in agents,
      'No ERROR logs':         not summary['has_errors'],
    }
    for label, result in checks.items():
      assert result, f"Validation failed: {label}"
