# core/logger.py - Centralized pipeline logger with SQLite persistence
"""
Pipeline Logger
===============
Persists every log entry emitted by the agents into a `pipeline_logs` SQLite
table so that historical runs can be reviewed and validated via the UI or tests.

Log entry schema
----------------
  id            INTEGER PRIMARY KEY
  invoice_id    INTEGER  (FK to invoices.id)
  run_id        TEXT     (UUID generated per pipeline run)
  agent         TEXT     (EXTRACTOR | MATCHER | EXCEPTION_HANDLER | SYSTEM)
  level         TEXT     (INFO | WARNING | ERROR)
  message       TEXT
  created_at    TEXT     (ISO-8601 timestamp)
"""

import sqlite3
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from core.config import SQLITE_DB_PATH


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
  conn = sqlite3.connect(SQLITE_DB_PATH)
  conn.row_factory = sqlite3.Row
  return conn


def _infer_agent(message: str) -> str:
  """Derive agent tag from the bracketed prefix in a log message."""
  m = re.match(r'\[([A-Z _]+)\]', message)
  if m:
    tag = m.group(1).strip()
    if 'EXTRACTOR' in tag:
      return 'EXTRACTOR'
    if 'MATCHER' in tag:
      return 'MATCHER'
    if 'EXCEPTION' in tag:
      return 'EXCEPTION_HANDLER'
  return 'SYSTEM'


def _infer_level(message: str) -> str:
  """Derive severity level from keywords in the message."""
  upper = message.upper()
  if 'ERROR' in upper or 'FAILED' in upper:
    return 'ERROR'
  if 'WARNING' in upper or 'WARN' in upper or 'LOW CONFIDENCE' in upper:
    return 'WARNING'
  return 'INFO'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def new_run_id() -> str:
  """Generate a unique run ID (UUID4) for a pipeline execution."""
  return str(uuid.uuid4())


def persist_logs(
  invoice_id: int,
  run_id: str,
  log_entries: List[str],
) -> None:
  """
  Persist a list of plain-text log entries (from ReconState["logs"]) to
  the `pipeline_logs` table.

  Args:
    invoice_id:  The integer PK of the invoice being processed.
    run_id:      UUID string for this specific pipeline run.
    log_entries: List of log strings as appended by the agent nodes.
  """
  conn = _get_conn()
  now = datetime.now(timezone.utc).isoformat()
  rows = [
    (
      invoice_id,
      run_id,
      _infer_agent(msg),
      _infer_level(msg),
      msg,
      now,
    )
    for msg in log_entries
  ]
  conn.executemany(
    """
    INSERT INTO pipeline_logs
      (invoice_id, run_id, agent, level, message, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    rows,
  )
  conn.commit()
  conn.close()


def log_entry(
  invoice_id: int,
  run_id: str,
  message: str,
  agent: Optional[str] = None,
  level: Optional[str] = None,
) -> None:
  """
  Write a single log entry directly (useful for system-level events).

  Args:
    invoice_id: PK of the invoice.
    run_id:     Pipeline run UUID.
    message:    Human-readable log text.
    agent:      Override agent tag (default: inferred from message).
    level:      Override level (default: inferred from message).
  """
  conn = _get_conn()
  conn.execute(
    """
    INSERT INTO pipeline_logs
      (invoice_id, run_id, agent, level, message, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    (
      invoice_id,
      run_id,
      agent or _infer_agent(message),
      level or _infer_level(message),
      message,
      datetime.now(timezone.utc).isoformat(),
    ),
  )
  conn.commit()
  conn.close()


# ---------------------------------------------------------------------------
# Query API  (used by Streamlit UI & tests)
# ---------------------------------------------------------------------------

def get_logs_for_invoice(invoice_id: int) -> List[dict]:
  """Return all log rows for a given invoice, newest first."""
  conn = _get_conn()
  rows = conn.execute(
    """
    SELECT id, invoice_id, run_id, agent, level, message, created_at
    FROM pipeline_logs
    WHERE invoice_id = ?
    ORDER BY id DESC
    """,
    (invoice_id,),
  ).fetchall()
  conn.close()
  return [dict(r) for r in rows]


def get_logs_for_run(run_id: str) -> List[dict]:
  """Return all log rows for a specific pipeline run (ordered by insertion)."""
  conn = _get_conn()
  rows = conn.execute(
    """
    SELECT id, invoice_id, run_id, agent, level, message, created_at
    FROM pipeline_logs
    WHERE run_id = ?
    ORDER BY id ASC
    """,
    (run_id,),
  ).fetchall()
  conn.close()
  return [dict(r) for r in rows]


def get_all_logs(
  level: Optional[str] = None,
  agent: Optional[str] = None,
  limit: int = 500,
) -> List[dict]:
  """
  Return recent log rows with optional level / agent filter.

  Args:
    level:  'INFO' | 'WARNING' | 'ERROR' | None (all)
    agent:  'EXTRACTOR' | 'MATCHER' | 'EXCEPTION_HANDLER' | 'SYSTEM' | None
    limit:  Maximum rows to return (default 500).
  """
  conn = _get_conn()
  clauses, params = [], []
  if level:
    clauses.append('level = ?')
    params.append(level)
  if agent:
    clauses.append('agent = ?')
    params.append(agent)
  where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
  params.append(limit)
  rows = conn.execute(
    f"""
    SELECT id, invoice_id, run_id, agent, level, message, created_at
    FROM pipeline_logs
    {where}
    ORDER BY id DESC
    LIMIT ?
    """,
    params,
  ).fetchall()
  conn.close()
  return [dict(r) for r in rows]


def get_run_summary(run_id: str) -> dict:
  """
  Return validation summary for a pipeline run:
    - total log entries
    - counts by level (INFO / WARNING / ERROR)
    - counts by agent
    - whether any ERROR or WARNING exists
  """
  logs = get_logs_for_run(run_id)
  summary = {
    'run_id': run_id,
    'total': len(logs),
    'by_level': {'INFO': 0, 'WARNING': 0, 'ERROR': 0},
    'by_agent': {},
    'has_errors': False,
    'has_warnings': False,
    'agents_executed': [],
  }
  for log in logs:
    lvl = log['level']
    agt = log['agent']
    summary['by_level'][lvl] = summary['by_level'].get(lvl, 0) + 1
    summary['by_agent'][agt] = summary['by_agent'].get(agt, 0) + 1
    if agt not in summary['agents_executed']:
      summary['agents_executed'].append(agt)
  summary['has_errors'] = summary['by_level']['ERROR'] > 0
  summary['has_warnings'] = summary['by_level']['WARNING'] > 0
  return summary
