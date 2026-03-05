# core/services.py - Business logic called by LangGraph agent nodes
import json
import hashlib
import time
from datetime import datetime, timezone
from typing import Tuple

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from .config import (
    azure_openai_client,
    OPENAI_MODEL,
    CONFIDENCE_THRESHOLD,
    PRICE_TOLERANCE_PCT,
    QTY_TOLERANCE_PCT,
    VENDOR_TOLERANCES,
)
from . import repositories as repo
from models.schemas import ExtractedInvoice, InvoiceLine


def _safe_ask_rules(question: str) -> str:
    """Call RAG safely — return a default rule string if RAG is unavailable."""
    try:
        from .rules_rag import ask_rules
        return ask_rules(question)
    except Exception:
        return "No matching rule found. Flag for manual review."


def compute_template_hash(invoice_json: dict) -> str:
    """Hash the structural keys of the invoice to detect template drift."""
    keys = sorted(invoice_json.keys())
    line_keys = sorted(
        invoice_json.get("line_items", [{}])[0].keys()
    ) if invoice_json.get("line_items") else []
    fingerprint = str(keys) + str(line_keys)
    return hashlib.md5(fingerprint.encode()).hexdigest()


def start_invoice_pipeline(
    raw_json: str, vendor_id: str,
    vendor_name: str, template_hash: str
) -> int:
    """Insert invoice and register template for drift detection."""
    invoice_id = repo.insert_invoice(raw_json, template_hash, vendor_id, vendor_name)
    repo.upsert_template(vendor_id, template_hash)
    return invoice_id


def run_extractor(invoice_id: int, invoice_json: dict) -> Tuple[dict, float]:
    """Use Azure OpenAI to extract and normalise invoice fields."""
    parser = PydanticOutputParser(pydantic_object=ExtractedInvoice)
    format_instructions = parser.get_format_instructions()

    system_msg = (
        "You are an invoice extraction specialist. "
        "Extract structured data from the invoice JSON.\n"
        f"{format_instructions}"
    )
    user_msg = f"Invoice JSON:\n{json.dumps(invoice_json, indent=2)}"

    response = azure_openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ],
    )

    raw_output = response.choices[0].message.content
    extracted: ExtractedInvoice = parser.parse(raw_output)

    # Confidence scoring
    confidence = 1.0
    if not extracted.invoice_number: confidence -= 0.1
    if not extracted.vendor_id:      confidence -= 0.2
    if not extracted.line_items:     confidence -= 0.5
    confidence = max(0.0, confidence)

    lines = [line.dict() for line in extracted.line_items]
    repo.insert_invoice_lines(invoice_id, lines)
    repo.update_invoice_status(invoice_id, "MATCHING", extraction_confidence=confidence)
    return extracted.dict(), confidence


def run_matcher(invoice_id: int, extracted_data: dict) -> Tuple[int, list]:
    """Match invoice lines to order lines using correct PO-scoped matching logic.

    Matching Logic (in order):
    1. Resolve exact PO by po_number + vendor_id → INVALID_PO if not found
    2. Scope order lines to THAT specific PO only (no cross-PO matching)
    3. Check for duplicate billing per order line → DUPLICATE_BILLING if over-reconciled
    4. Apply per-vendor tolerances (not flat global tolerance)
    5. Log WITHIN_TOLERANCE as INFO discrepancy for full audit trail
    """
    vendor_id  = extracted_data.get("vendor_id", "")
    po_number  = extracted_data.get("po_number", "")
    started_at = datetime.now(timezone.utc).isoformat()

    # Create reconciliation record
    recon_id = repo.create_reconciliation(invoice_id, po_number, started_at)
    discrepancies = []

    # ── Step 1: Resolve exact PO ──────────────────────────────────────────────
    order = repo.get_order_by_po_and_vendor(po_number, vendor_id)
    if not order:
        rule = _safe_ask_rules(
            f"Invoice references PO '{po_number}' for vendor '{vendor_id}' "
            "but no matching open order exists. What should happen?"
        )
        discrepancies.append({
            "type": "INVALID_PO",
            "product_code": None,
            "po_number": po_number,
            "rule": rule,
        })
        overall = "INVALID_PO"
        completed_at = datetime.now(timezone.utc).isoformat()
        latency_ms = int(
            (datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at))
            .total_seconds() * 1000
        )
        repo.update_reconciliation(recon_id, overall, 0.0, completed_at, latency_ms)
        return recon_id, discrepancies

    # ── Step 2: Build SKU map scoped to THIS order only ───────────────────────
    order_lines   = repo.get_order_lines(order["id"])
    invoice_lines = repo.get_invoice_lines(invoice_id)

    # Guard against duplicate SKUs within same order (data quality issue)
    order_map: dict = {}
    for ol in order_lines:
        pcode = ol["product_code"]
        if pcode in order_map:
            # Keep first, log warning — shouldn't happen in clean data
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "Duplicate product_code '%s' found in order %s — keeping first occurrence",
                pcode, order["id"],
            )
            continue
        order_map[pcode] = ol

    # ── Step 3, 4 & 5: Per-line matching ─────────────────────────────────────
    # Get per-vendor tolerances, fall back to global config defaults
    vendor_tols = VENDOR_TOLERANCES.get(vendor_id, {})
    price_tol   = vendor_tols.get("price_pct", PRICE_TOLERANCE_PCT)
    qty_tol     = vendor_tols.get("qty_pct",   QTY_TOLERANCE_PCT)

    for il in invoice_lines:
        pcode = il.get("product_code", "")
        ol    = order_map.get(pcode)

        # NO_MATCH — SKU not in this PO
        if not ol:
            rule = _safe_ask_rules(
                f"Product code '{pcode}' not found in PO '{po_number}' "
                f"for vendor '{vendor_id}'. What should happen?"
            )
            repo.insert_reconciliation_line(
                recon_id, il["id"], None, "NO_MATCH", 0, 0, rule
            )
            discrepancies.append({"type": "NO_MATCH", "product_code": pcode, "rule": rule})
            continue

        # DUPLICATE_BILLING — check already reconciled quantity
        already_reconciled = repo.get_already_reconciled_qty(ol["id"])
        if already_reconciled + il["quantity"] > ol["ordered_qty"] * 1.001:  # tiny float buffer
            rule = _safe_ask_rules(
                f"Product '{pcode}': ordered_qty={ol['ordered_qty']}, "
                f"already_reconciled={already_reconciled}, "
                f"new invoice_qty={il['quantity']}. Duplicate billing detected."
            )
            repo.insert_reconciliation_line(
                recon_id, il["id"], ol["id"], "DUPLICATE_BILLING", 0, 0, rule
            )
            discrepancies.append({
                "type": "DUPLICATE_BILLING",
                "product_code": pcode,
                "already_reconciled_qty": already_reconciled,
                "invoice_qty": il["quantity"],
                "ordered_qty": ol["ordered_qty"],
                "rule": rule,
                "invoice_line_id": il["id"],
                "order_line_id": ol["id"],
            })
            continue

        # Calculate differences
        qty_diff   = il["quantity"]   - ol["ordered_qty"]
        price_diff = il["unit_price"] - ol["unit_price"]
        qty_pct    = abs(qty_diff)   / ol["ordered_qty"]  if ol["ordered_qty"]  else 0
        price_pct  = abs(price_diff) / ol["unit_price"]   if ol["unit_price"]   else 0

        if qty_pct <= qty_tol and price_pct <= price_tol:
            if qty_diff == 0 and price_diff == 0:
                status = "MATCHED"
                rule   = "Exact match"
            else:
                # WITHIN_TOLERANCE — auto-approve but create audit trail
                status = "WITHIN_TOLERANCE"
                rule = (
                    f"Within vendor tolerance (qty_tol={qty_tol:.0%}, "
                    f"price_tol={price_tol:.0%}): "
                    f"qty_diff={qty_diff:+}, price_diff={price_diff:+.4f}"
                )
                discrepancies.append({
                    "type": "TOLERANCE_VARIANCE",
                    "product_code": pcode,
                    "qty_diff": qty_diff,
                    "price_diff": round(price_diff, 4),
                    "rule": rule,
                    "invoice_line_id": il["id"],
                    "order_line_id": ol["id"],
                })
        else:
            rule = _safe_ask_rules(
                f"Product '{pcode}' (vendor {vendor_id}): "
                f"invoice qty={il['quantity']} vs order qty={ol['ordered_qty']} "
                f"(diff={qty_pct:.1%}), "
                f"invoice price={il['unit_price']} vs order price={ol['unit_price']} "
                f"(diff={price_pct:.1%}). "
                f"Vendor tolerances: qty={qty_tol:.0%}, price={price_tol:.0%}. "
                "What rule applies?"
            )
            status = "OUT_OF_TOLERANCE"
            discrepancies.append({
                "type": "QUANTITY_MISMATCH" if qty_pct > qty_tol else "PRICE_MISMATCH",
                "product_code": pcode,
                "qty_diff": qty_diff,
                "price_diff": round(price_diff, 4),
                "rule": rule,
                "invoice_line_id": il["id"],
                "order_line_id": ol["id"],
            })

        repo.insert_reconciliation_line(
            recon_id, il["id"], ol["id"], status, qty_diff, price_diff, rule
        )

    # ── Overall result ────────────────────────────────────────────────────────
    # TOLERANCE_VARIANCE discrepancies don't count against overall status
    hard_discrepancies = [
        d for d in discrepancies
        if d["type"] not in ("TOLERANCE_VARIANCE",)
    ]
    if not hard_discrepancies:
        overall = "MATCHED"
    elif len(hard_discrepancies) < len(invoice_lines):
        overall = "PARTIAL_MATCH"
    else:
        overall = "MISMATCH"

    # Confidence excludes TOLERANCE_VARIANCE from penalty
    confidence = 1.0 - (len(hard_discrepancies) / max(len(invoice_lines), 1))
    completed_at = datetime.now(timezone.utc).isoformat()
    latency_ms = int(
        (datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at))
        .total_seconds() * 1000
    )
    repo.update_reconciliation(recon_id, overall, confidence, completed_at, latency_ms)
    return recon_id, discrepancies


def handle_exceptions(recon_id: int, discrepancies: list):
    """Auto-approve, block, or flag for human review based on discrepancy type."""
    SEVERITY_MAP = {
        "NO_MATCH":           ("CRITICAL", "BLOCKED"),
        "INVALID_PO":         ("CRITICAL", "BLOCKED"),
        "DUPLICATE_BILLING":  ("CRITICAL", "BLOCKED"),
        "QUANTITY_MISMATCH":  ("WARNING",  "NEEDS_REVIEW"),
        "PRICE_MISMATCH":     ("WARNING",  "NEEDS_REVIEW"),
        "TOLERANCE_VARIANCE": ("INFO",     "AUTO_APPROVED"),
    }
    for d in discrepancies:
        exc_type = d.get("type", "UNKNOWN")
        severity, auto_action = SEVERITY_MAP.get(exc_type, ("WARNING", "NEEDS_REVIEW"))
        description = (
            f"{exc_type}: product={d.get('product_code')}, "
            f"qty_diff={d.get('qty_diff', 'N/A')}, "
            f"price_diff={d.get('price_diff', 'N/A')}. "
            f"Rule: {d.get('rule', 'N/A')}"
        )
        repo.insert_exception(recon_id, exc_type, severity, description, auto_action)
