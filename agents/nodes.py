# agents/nodes.py - Extractor, Matcher, Exception Handler nodes
from .state import ReconState
from core import repositories as repo
from core import logger as pipeline_logger
from core.config import CONFIDENCE_THRESHOLD
from core.services import run_extractor, run_matcher, handle_exceptions
from langchain_openai import ChatOpenAI
from core.config import OPENAI_MODEL
import time

llm = ChatOpenAI(model=OPENAI_MODEL)


def extractor_node(state: ReconState) -> ReconState:
    """Extracts and normalizes invoice data using GPT structured output."""
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

    extracted, confidence = run_extractor(invoice_id, state["invoice_json"], llm)
    msg_done = f"[EXTRACTOR] Completed. Confidence={confidence:.2f}"
    logs.append(msg_done)
    pipeline_logger.log_entry(invoice_id=invoice_id, run_id=run_id, message=msg_done)

    if confidence < CONFIDENCE_THRESHOLD:
        msg_warn = f"[EXTRACTOR] WARNING: Low confidence ({confidence:.2f}) - flagged for human review"
        logs.append(msg_warn)
        pipeline_logger.log_entry(invoice_id=invoice_id, run_id=run_id, message=msg_warn)

    state["extracted_data"] = extracted
    state["logs"] = logs
    state["run_id"] = run_id
    state["pipeline_status"] = "MATCHING"
    repo.update_invoice_status(invoice_id, "MATCHING", extraction_confidence=confidence)
    return state


def matcher_node(state: ReconState) -> ReconState:
    """Matches extracted invoice lines against orders DB using rules + RAG."""
    invoice_id = state["invoice_id"]
    run_id = state.get("run_id") or pipeline_logger.new_run_id()
    repo.update_invoice_status(invoice_id, "MATCHING")
    logs = state.get("logs", [])
    logs.append("[MATCHER] Starting order matching...")
    pipeline_logger.log_entry(invoice_id=invoice_id, run_id=run_id,
                              message="[MATCHER] Starting order matching...")

    start = time.time()
    recon_id, discrepancies = run_matcher(invoice_id, state["extracted_data"], llm)
    latency_ms = int((time.time() - start) * 1000)

    msg = f"[MATCHER] Found {len(discrepancies)} discrepancies. Latency={latency_ms}ms"
    logs.append(msg)
    pipeline_logger.log_entry(invoice_id=invoice_id, run_id=run_id, message=msg)

    for d in discrepancies:
        detail = (
            f"[MATCHER] Discrepancy on {d.get('field','?')}: "
            f"invoice={d.get('invoice_value','?')} po={d.get('po_value','?')}"
        )
        logs.append(detail)
        pipeline_logger.log_entry(invoice_id=invoice_id, run_id=run_id, message=detail)

    state["reconciliation_id"] = recon_id
    state["discrepancies"] = discrepancies
    state["logs"] = logs
    state["run_id"] = run_id
    state["pipeline_status"] = "EXCEPTION_HANDLING"
    repo.update_invoice_status(invoice_id, "EXCEPTION_HANDLING")
    return state


def exception_handler_node(state: ReconState) -> ReconState:
    """Handles exceptions: auto-approve, block, or flag for human review."""
    invoice_id = state["invoice_id"]
    run_id = state.get("run_id") or pipeline_logger.new_run_id()
    logs = state.get("logs", [])
    logs.append("[EXCEPTION HANDLER] Processing exceptions...")
    pipeline_logger.log_entry(invoice_id=invoice_id, run_id=run_id,
                              message="[EXCEPTION HANDLER] Processing exceptions...")

    handle_exceptions(
        state["reconciliation_id"],
        state.get("discrepancies", []),
        llm
    )

    msg_done = "[EXCEPTION HANDLER] Done. Pipeline completed."
    logs.append(msg_done)
    pipeline_logger.log_entry(invoice_id=invoice_id, run_id=run_id, message=msg_done)

    state["logs"] = logs
    state["run_id"] = run_id
    state["pipeline_status"] = "COMPLETED"
    repo.update_invoice_status(invoice_id, "COMPLETED")
    return state
