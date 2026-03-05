# agents/nodes.py - Extractor, Matcher, Exception Handler nodes
from .state import ReconState
from core import repositories as repo
from core import logger as pipeline_logger
from core.config import CONFIDENCE_THRESHOLD, azure_openai_client, OPENAI_MODEL
from core.services import run_extractor, run_matcher, handle_exceptions
import time


def extractor_node(state: ReconState) -> ReconState:
    """Extracts and normalizes invoice data using Azure OpenAI structured output."""
    invoice_id = state["invoice_id"]
    repo.update_invoice_status(invoice_id, "EXTRACTING")
    logs = state.get("logs", [])
    run_id = state.get("run_id") or pipeline_logger.new_run_id()
    logs.append("[EXTRACTOR] Starting invoice extraction...")

    # Single start-of-node entry directly to DB so the run_id is stored early
    pipeline_logger.log_entry(
        invoice_id=invoice_id,
        run_id=run_id,
        message="[EXTRACTOR] Starting invoice extraction...",
    )

    extracted, confidence = run_extractor(invoice_id, state["invoice_json"])
    msg_done = f"[EXTRACTOR] Completed. Confidence={confidence:.2f}"
    logs.append(msg_done)
    pipeline_logger.log_entry(invoice_id=invoice_id, run_id=run_id, message=msg_done)

    if confidence < CONFIDENCE_THRESHOLD:
        msg_warn = (
            f"[EXTRACTOR] WARNING: Low confidence ({confidence:.2f})"
            " - flagged for human review"
        )
        logs.append(msg_warn)
        pipeline_logger.log_entry(
            invoice_id=invoice_id, run_id=run_id, message=msg_warn
        )

    state["extracted_data"] = extracted
    state["logs"] = logs
    state["run_id"] = run_id
    state["pipeline_status"] = "MATCHING"
    repo.update_invoice_status(
        invoice_id, "MATCHING", extraction_confidence=confidence
    )
    return state


def matcher_node(state: ReconState) -> ReconState:
    """Matches extracted invoice lines against orders DB using rules + RAG."""
    invoice_id = state["invoice_id"]
    run_id = state.get("run_id") or pipeline_logger.new_run_id()
    repo.update_invoice_status(invoice_id, "MATCHING")
    logs = state.get("logs", [])
    logs.append("[MATCHER] Starting order matching...")
    pipeline_logger.log_entry(
        invoice_id=invoice_id,
        run_id=run_id,
        message="[MATCHER] Starting order matching...",
    )

    start = time.time()
    recon_id, discrepancies = run_matcher(invoice_id, state["extracted_data"])
    latency_ms = int((time.time() - start) * 1000)

    msg = (
        f"[MATCHER] Done. recon_id={recon_id}, "
        f"discrepancies={len(discrepancies)}, latency={latency_ms}ms"
    )
    logs.append(msg)
    pipeline_logger.log_entry(invoice_id=invoice_id, run_id=run_id, message=msg)

    state["recon_id"] = recon_id
    state["discrepancies"] = discrepancies
    state["logs"] = logs
    state["run_id"] = run_id
    state["pipeline_status"] = "EXCEPTION_HANDLING"
    return state


def exception_handler_node(state: ReconState) -> ReconState:
    """Auto-approve, block, or flag discrepancies for human review."""
    recon_id = state["recon_id"]
    discrepancies = state.get("discrepancies", [])
    run_id = state.get("run_id") or pipeline_logger.new_run_id()
    invoice_id = state["invoice_id"]
    logs = state.get("logs", [])

    logs.append(
        f"[EXCEPTION_HANDLER] Processing {len(discrepancies)} discrepancies..."
    )
    pipeline_logger.log_entry(
        invoice_id=invoice_id,
        run_id=run_id,
        message=f"[EXCEPTION_HANDLER] Processing {len(discrepancies)} discrepancies...",
    )

    handle_exceptions(recon_id, discrepancies)

    status = "COMPLETED"
    msg_done = f"[EXCEPTION_HANDLER] Done. Final status={status}"
    logs.append(msg_done)
    pipeline_logger.log_entry(
        invoice_id=invoice_id, run_id=run_id, message=msg_done
    )

    repo.update_invoice_status(invoice_id, status)
    state["pipeline_status"] = status
    state["logs"] = logs
    return state
