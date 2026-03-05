# core/repositories.py - CRUD operations for all DB tables
from typing import Optional
from .db import get_connection


# ── Invoices ─────────────────────────────────────────────────────────────────

def insert_invoice(raw_json: str, template_hash: str, vendor_id: str,
                  vendor_name: str, invoice_number: str = "") -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO invoices
               (invoice_number, vendor_id, vendor_name, raw_json, template_hash, status)
               VALUES (?, ?, ?, ?, ?, 'UPLOADED')""",
            (invoice_number, vendor_id, vendor_name, raw_json, template_hash),
        )
        return cur.lastrowid


def update_invoice_status(invoice_id: int, status: str,
                          extraction_confidence: Optional[float] = None):
    with get_connection() as conn:
        if extraction_confidence is not None:
            conn.execute(
                "UPDATE invoices SET status=?, extraction_confidence=? WHERE id=?",
                (status, extraction_confidence, invoice_id),
            )
        else:
            conn.execute("UPDATE invoices SET status=? WHERE id=?",
                         (status, invoice_id))


def update_invoice_extracted_fields(invoice_id: int, currency: Optional[str],
                                    invoice_date: Optional[str]):
    """Persist currency and invoice_date extracted by the AI onto the invoice record."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE invoices SET currency=?, invoice_date=? WHERE id=?",
            (currency, invoice_date, invoice_id),
        )


def get_invoice_by_id(invoice_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM invoices WHERE id=?",
                           (invoice_id,)).fetchone()
        return dict(row) if row else None


def get_all_invoices() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM invoices ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


# ── Invoice Lines ─────────────────────────────────────────────────────────────

def insert_invoice_lines(invoice_id: int, lines: list[dict]):
    with get_connection() as conn:
        # Use explicit .get() for each field so callers don't need to supply
        # optional fields (description, tax_rate) — prevents binding errors
        # from SQLite named parameters when keys are absent.
        conn.executemany(
            """INSERT INTO invoice_lines
               (invoice_id, line_number, product_code, description, quantity, unit_price, tax_rate)
               VALUES (:invoice_id, :line_number, :product_code, :description,
                       :quantity, :unit_price, :tax_rate)""",
            [
                {
                    "invoice_id": invoice_id,
                    "line_number": line.get("line_number"),
                    "product_code": line.get("product_code"),
                    "description": line.get("description"),
                    "quantity": line.get("quantity"),
                    "unit_price": line.get("unit_price"),
                    "tax_rate": line.get("tax_rate"),
                }
                for line in lines
            ],
        )


def get_invoice_lines(invoice_id: int) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM invoice_lines WHERE invoice_id=?", (invoice_id,)).fetchall()
        return [dict(r) for r in rows]


# ── Orders ────────────────────────────────────────────────────────────────────

def get_all_orders() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_order_by_id(order_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id=?",
                           (order_id,)).fetchone()
        return dict(row) if row else None


def get_order_lines(order_id: int) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM order_lines WHERE order_id=?",
            (order_id,)).fetchall()
        return [dict(r) for r in rows]


def get_order_by_po_and_vendor(po_number: str, vendor_id: str) -> Optional[dict]:
    """Fetch a single OPEN/PARTIALLY_RECEIVED order matching both po_number AND vendor_id."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM orders
               WHERE po_number=? AND vendor_id=?
               AND status IN ('OPEN','PARTIALLY_RECEIVED')""",
            (po_number, vendor_id),
        ).fetchone()
        return dict(row) if row else None


def get_already_reconciled_qty(order_line_id: int) -> float:
    """Sum invoice quantities already successfully matched against this order line.
    Used to detect duplicate billing."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(il.quantity), 0) as reconciled_qty
               FROM reconciliation_lines rl
               JOIN invoice_lines il ON rl.invoice_line_id = il.id
               WHERE rl.order_line_id = ?
               AND rl.match_status IN ('MATCHED', 'WITHIN_TOLERANCE')""",
            (order_line_id,),
        ).fetchone()
        return float(row["reconciled_qty"]) if row else 0.0


def get_order_candidates(vendor_id: str) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT o.po_number, o.vendor_id, o.currency,
                      ol.id AS order_line_id, ol.line_number,
                      ol.product_code, ol.description,
                      ol.ordered_qty, ol.unit_price, ol.tax_rate
               FROM orders o
               JOIN order_lines ol ON o.id = ol.order_id
               WHERE o.vendor_id = ? AND o.status IN ('OPEN','PARTIALLY_RECEIVED')""",
            (vendor_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Reconciliations ───────────────────────────────────────────────────────────

def create_reconciliation(invoice_id: int, po_number: str,
                          started_at: str) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO reconciliations (invoice_id, po_number, overall_status, started_at)
               VALUES (?, ?, 'IN_PROGRESS', ?)""",
            (invoice_id, po_number, started_at),
        )
        return cur.lastrowid


def update_reconciliation(recon_id: int, overall_status: str,
                          confidence: float, completed_at: str,
                          latency_ms: int):
    with get_connection() as conn:
        conn.execute(
            """UPDATE reconciliations
               SET overall_status=?, reconciliation_confidence=?,
                   completed_at=?, latency_ms=?
               WHERE id=?""",
            (overall_status, confidence, completed_at, latency_ms, recon_id),
        )


def get_all_reconciliations() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM reconciliations ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


def get_reconciliation_by_id(recon_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM reconciliations WHERE id=?",
                           (recon_id,)).fetchone()
        return dict(row) if row else None


def get_reconciliations_for_invoice(invoice_id: int) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM reconciliations WHERE invoice_id=? ORDER BY id DESC",
            (invoice_id,)).fetchall()
        return [dict(r) for r in rows]


def insert_reconciliation_line(recon_id: int, invoice_line_id: int,
                               order_line_id: int, match_status: str,
                               qty_diff: float, price_diff: float,
                               applied_rule: str):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO reconciliation_lines
               (reconciliation_id, invoice_line_id, order_line_id,
                match_status, quantity_diff, price_diff, applied_rule)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (recon_id, invoice_line_id, order_line_id,
             match_status, qty_diff, price_diff, applied_rule),
        )


def get_reconciliation_lines(recon_id: int) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM reconciliation_lines WHERE reconciliation_id=?",
            (recon_id,)).fetchall()
        return [dict(r) for r in rows]


# ── Exceptions ────────────────────────────────────────────────────────────────

def insert_exception(
    recon_id: int,
    exc_type: str,
    severity: str,
    description: str,
    auto_action: str,
    invoice_id: int = None,
    invoice_number: str = None,
    vendor_id: str = None,
    vendor_name: str = None,
    po_number: str = None,
    product_code: str = None,
):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO exceptions
               (reconciliation_id, type, severity, description, auto_action,
                invoice_id, invoice_number, vendor_id, vendor_name, po_number, product_code)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (recon_id, exc_type, severity, description, auto_action,
             invoice_id, invoice_number, vendor_id, vendor_name, po_number, product_code),
        )


def get_unresolved_exceptions() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM exceptions WHERE resolved=0 ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_exceptions() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM exceptions ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


def get_unresolved_exceptions_enriched() -> list:
    """Return unresolved exceptions with full invoice/vendor/PO context joined in."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT
                e.id,
                e.reconciliation_id,
                e.invoice_id,
                COALESCE(e.invoice_number, i.invoice_number) AS invoice_number,
                COALESCE(e.vendor_id,      i.vendor_id)      AS vendor_id,
                COALESCE(e.vendor_name,    i.vendor_name)    AS vendor_name,
                COALESCE(e.po_number,      r.po_number)      AS po_number,
                e.product_code,
                e.type,
                e.severity,
                e.description,
                e.auto_action,
                e.resolved,
                e.resolved_by,
                e.resolved_at,
                i.extraction_confidence,
                i.status AS invoice_status
               FROM exceptions e
               LEFT JOIN reconciliations r ON e.reconciliation_id = r.id
               LEFT JOIN invoices i        ON r.invoice_id = i.id
               WHERE e.resolved = 0
               ORDER BY
                 CASE e.severity WHEN 'CRITICAL' THEN 0 WHEN 'WARNING' THEN 1 ELSE 2 END,
                 e.id DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_exceptions_enriched() -> list:
    """Return all exceptions with full invoice/vendor/PO context joined in."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT
                e.id,
                e.reconciliation_id,
                e.invoice_id,
                COALESCE(e.invoice_number, i.invoice_number) AS invoice_number,
                COALESCE(e.vendor_id,      i.vendor_id)      AS vendor_id,
                COALESCE(e.vendor_name,    i.vendor_name)    AS vendor_name,
                COALESCE(e.po_number,      r.po_number)      AS po_number,
                e.product_code,
                e.type,
                e.severity,
                e.description,
                e.auto_action,
                e.resolved,
                e.resolved_by,
                e.resolved_at,
                i.extraction_confidence,
                i.status AS invoice_status
               FROM exceptions e
               LEFT JOIN reconciliations r ON e.reconciliation_id = r.id
               LEFT JOIN invoices i        ON r.invoice_id = i.id
               ORDER BY
                 CASE e.severity WHEN 'CRITICAL' THEN 0 WHEN 'WARNING' THEN 1 ELSE 2 END,
                 e.id DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_exceptions_for_reconciliation(recon_id: int) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM exceptions WHERE reconciliation_id=? ORDER BY id DESC",
            (recon_id,)).fetchall()
        return [dict(r) for r in rows]


def resolve_exception(exception_id: int, resolved_by: str, resolved_at: str):
    with get_connection() as conn:
        conn.execute(
            """UPDATE exceptions SET resolved=1, resolved_by=?, resolved_at=?
               WHERE id=?""",
            (resolved_by, resolved_at, exception_id),
        )


# ── Templates / Drift ─────────────────────────────────────────────────────────

def get_latest_template(vendor_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM invoice_templates
               WHERE vendor_id=? AND is_active=1
               ORDER BY last_seen_at DESC LIMIT 1""",
            (vendor_id,),
        ).fetchone()
        return dict(row) if row else None


def get_all_templates() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM invoice_templates ORDER BY last_seen_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_template(vendor_id: str, template_hash: str):
    existing = get_latest_template(vendor_id)
    with get_connection() as conn:
        if existing and existing["template_hash"] == template_hash:
            conn.execute(
                "UPDATE invoice_templates SET last_seen_at=CURRENT_TIMESTAMP WHERE id=?",
                (existing["id"],),
            )
        else:
            conn.execute(
                """INSERT INTO invoice_templates (vendor_id, template_hash)
                   VALUES (?, ?)""",
                (vendor_id, template_hash),
            )


# ── Metrics ───────────────────────────────────────────────────────────────────

def log_metrics_run(invoices_processed: int, mismatch_rate: float,
                    avg_confidence: float, avg_latency_ms: float):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO metrics_runs
               (invoices_processed, mismatch_rate,
                avg_extraction_confidence, avg_reconciliation_latency_ms)
               VALUES (?, ?, ?, ?)""",
            (invoices_processed, mismatch_rate, avg_confidence, avg_latency_ms),
        )


def get_metrics_history() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM metrics_runs ORDER BY run_timestamp DESC LIMIT 50"
        ).fetchall()
        return [dict(r) for r in rows]
