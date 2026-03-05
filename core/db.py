# core/db.py - SQLite connection and schema initialization
import sqlite3
from contextlib import contextmanager
from .config import SQLITE_DB_PATH


@contextmanager
def get_connection():
    """Context manager for SQLite connections with auto-commit and close."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    schema = """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_number TEXT UNIQUE NOT NULL,
        vendor_id TEXT NOT NULL,
        vendor_name TEXT,
        order_date TEXT,
        status TEXT DEFAULT 'OPEN',
        currency TEXT DEFAULT 'USD',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS order_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        line_number INTEGER NOT NULL,
        product_code TEXT NOT NULL,
        description TEXT,
        ordered_qty REAL NOT NULL,
        unit_price REAL NOT NULL,
        tax_rate REAL DEFAULT 0.0,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    );

    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number TEXT,
        vendor_id TEXT NOT NULL,
        vendor_name TEXT,
        -- invoice_date and currency columns removed (never populated; migration note:
        --   ALTER TABLE invoices DROP COLUMN invoice_date / currency on existing DBs if needed)
        raw_json TEXT NOT NULL,
        extraction_confidence REAL,
        template_hash TEXT,
        status TEXT DEFAULT 'UPLOADED',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS invoice_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        line_number INTEGER,
        product_code TEXT,
        description TEXT,
        quantity REAL,
        unit_price REAL,
        tax_rate REAL,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id)
    );

    CREATE TABLE IF NOT EXISTS reconciliations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        po_number TEXT,
        overall_status TEXT,
        reconciliation_confidence REAL,
        started_at TEXT,
        completed_at TEXT,
        latency_ms INTEGER,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id)
    );

    CREATE TABLE IF NOT EXISTS reconciliation_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reconciliation_id INTEGER NOT NULL,
        invoice_line_id INTEGER,
        order_line_id INTEGER,
        match_status TEXT,
        quantity_diff REAL,
        price_diff REAL,
        applied_rule TEXT,
        FOREIGN KEY (reconciliation_id) REFERENCES reconciliations(id)
    );

    CREATE TABLE IF NOT EXISTS exceptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reconciliation_id INTEGER NOT NULL,
        type TEXT,
        severity TEXT,
        description TEXT,
        auto_action TEXT,
        resolved INTEGER DEFAULT 0,
        resolved_by TEXT,
        resolved_at TEXT,
        FOREIGN KEY (reconciliation_id) REFERENCES reconciliations(id)
    );

    CREATE TABLE IF NOT EXISTS invoice_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_id TEXT NOT NULL,
        template_hash TEXT NOT NULL,
        first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS metrics_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        invoices_processed INTEGER,
        mismatch_rate REAL,
        avg_extraction_confidence REAL,
        avg_reconciliation_latency_ms REAL
    );
    
    CREATE TABLE IF NOT EXISTS pipeline_logs (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        run_id     TEXT    NOT NULL,
        agent      TEXT    NOT NULL DEFAULT 'SYSTEM',
        level      TEXT    NOT NULL DEFAULT 'INFO',
        message    TEXT    NOT NULL,
        created_at TEXT    DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id)
    );

    CREATE INDEX IF NOT EXISTS idx_pipeline_logs_invoice
        ON pipeline_logs (invoice_id);

    CREATE INDEX IF NOT EXISTS idx_pipeline_logs_run
        ON pipeline_logs (run_id);
    """
    with get_connection() as conn:
        conn.executescript(schema)
    print(f"Database initialized at {SQLITE_DB_PATH}")
