# agents/nodes.py - Extractor, Matcher, Exception Handler nodes
from .state import ReconState
from core import repositories as repo
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
    logs.append("[EXTRACTOR] Starting invoice extraction...")

    extracted, confidence = run_extractor(invoice_id, state["invoice_json"], llm)

    logs.append(f"[EXTRACTOR] Completed. Confidence={confidence:.2f}")
    if confidence < CONFIDENCE_THRESHOLD:
        logs.append(f"[EXTRACTOR] WARNING: Low confidence ({confidence:.2f}) - flagged for human review")

    state["extracted_data"] = extracted
    state["logs"] = logs
    state["pipeline_status"] = "MATCHING"
    repo.update_invoice_status(invoice_id, "MATCHING", extraction_confidence=confidence)
    return state


def matcher_node(state: ReconState) -> ReconState:
    """Matches extracted invoice lines against orders DB using rules + RAG."""
    invoice_id = state["invoice_id"]
    repo.update_invoice_status(invoice_id, "MATCHING")
    logs = state.get("logs", [])
    logs.append("[MATCHER] Starting order matching...")

    start = time.time()
    recon_id, discrepancies = run_matcher(invoice_id, state["extracted_data"], llm)
    latency_ms = int((time.time() - start) * 1000)

    logs.append(f"[MATCHER] Found {len(discrepancies)} discrepancies. Latency={latency_ms}ms")

    state["reconciliation_id"] = recon_id
    state["discrepancies"] = discrepancies
    state["logs"] = logs
    state["pipeline_status"] = "EXCEPTION_HANDLING"
    repo.update_invoice_status(invoice_id, "EXCEPTION_HANDLING")
    return state


def exception_handler_node(state: ReconState) -> ReconState:
    """Handles exceptions: auto-approve, block, or flag for human review."""
    invoice_id = state["invoice_id"]
    logs = state.get("logs", [])
    logs.append("[EXCEPTION HANDLER] Processing exceptions...")

    handle_exceptions(
        state["reconciliation_id"],
        state.get("discrepancies", []),
        llm
    )

    logs.append("[EXCEPTION HANDLER] Done. Pipeline completed.")
    state["logs"] = logs
    state["pipeline_status"] = "COMPLETED"
    repo.update_invoice_status(invoice_id, "COMPLETED")
    return state
