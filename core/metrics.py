# core/metrics.py - Observability helpers for the reconciliation pipeline
from . import repositories as repo
from .db import get_connection


def compute_and_log_run_metrics(invoice_ids: list[int]):
    """Compute per-run metrics from DB and persist to metrics_runs table."""
    if not invoice_ids:
        return

    invoices = [repo.get_invoice_by_id(iid) for iid in invoice_ids]
    invoices = [i for i in invoices if i is not None]

    # avg extraction confidence
    confidences = [i["extraction_confidence"] for i in invoices if i["extraction_confidence"] is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    # get reconciliations for these invoices
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM reconciliations WHERE invoice_id IN ({}) ".format(
                ",".join(["?" for _ in invoice_ids])
            ),
            invoice_ids,
        ).fetchall()
        recons = [dict(r) for r in rows]

    mismatches = sum(1 for r in recons if r["overall_status"] == "MISMATCH")
    mismatch_rate = mismatches / len(recons) if recons else 0.0

    latencies = [r["latency_ms"] for r in recons if r["latency_ms"] is not None]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    repo.log_metrics_run(
        invoices_processed=len(invoice_ids),
        mismatch_rate=mismatch_rate,
        avg_confidence=avg_confidence,
        avg_latency_ms=avg_latency,
    )

    return {
        "invoices_processed": len(invoice_ids),
        "mismatch_rate": mismatch_rate,
        "avg_extraction_confidence": avg_confidence,
        "avg_reconciliation_latency_ms": avg_latency,
    }


def get_dashboard_metrics() -> dict:
    """Get latest metrics summary for Streamlit dashboard."""
    history = repo.get_metrics_history()
    if not history:
        return {
            "total_runs": 0,
            "avg_mismatch_rate": 0.0,
            "avg_confidence": 0.0,
            "avg_latency_ms": 0.0,
        }
    return {
        "total_runs": len(history),
        "avg_mismatch_rate": sum(r["mismatch_rate"] for r in history) / len(history),
        "avg_confidence": sum(r["avg_extraction_confidence"] for r in history) / len(history),
        "avg_latency_ms": sum(r["avg_reconciliation_latency_ms"] for r in history) / len(history),
        "history": history,
    }
