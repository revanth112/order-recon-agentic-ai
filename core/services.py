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
    """Match invoice lines to order lines, apply tolerance rules."""
    vendor_id  = extracted_data.get("vendor_id", "")
    po_number  = extracted_data.get("po_number", "")
    started_at = datetime.now(timezone.utc).isoformat()

    order_lines   = repo.get_order_candidates(vendor_id)
    invoice_lines = repo.get_invoice_lines(invoice_id)
    recon_id      = repo.create_reconciliation(invoice_id, po_number, started_at)

    discrepancies = []
    order_map = {ol["product_code"]: ol for ol in order_lines}

    for il in invoice_lines:
        pcode = il.get("product_code", "")
        ol    = order_map.get(pcode)

        if not ol:
            rule = _safe_ask_rules(
                f"What should happen when product code '{pcode}' "
                "is not found in any open PO?"
            )
            repo.insert_reconciliation_line(
                recon_id, il["id"], None, "NO_MATCH", 0, 0, rule
            )
            discrepancies.append({"type": "NO_MATCH", "product_code": pcode, "rule": rule})
            continue

        qty_diff   = il["quantity"]   - ol["ordered_qty"]
        price_diff = il["unit_price"] - ol["unit_price"]
        qty_pct    = abs(qty_diff)   / ol["ordered_qty"]  if ol["ordered_qty"]  else 0
        price_pct  = abs(price_diff) / ol["unit_price"]   if ol["unit_price"]   else 0

        if qty_pct <= QTY_TOLERANCE_PCT and price_pct <= PRICE_TOLERANCE_PCT:
            status = "MATCHED" if qty_diff == 0 and price_diff == 0 else "WITHIN_TOLERANCE"
            rule   = "Within tolerance limits"
        else:
            rule = _safe_ask_rules(
                f"Product '{pcode}': invoice qty={il['quantity']} vs order qty={ol['ordered_qty']}, "
                f"invoice price={il['unit_price']} vs order price={ol['unit_price']}. What rule applies?"
            )
            status = "OUT_OF_TOLERANCE"
            discrepancies.append({
                "type": "QUANTITY_MISMATCH" if qty_pct > QTY_TOLERANCE_PCT else "PRICE_MISMATCH",
                "product_code": pcode,
                "qty_diff": qty_diff,
                "price_diff": price_diff,
                "rule": rule,
                "invoice_line_id": il["id"],
                "order_line_id":   ol["order_line_id"],
            })

        repo.insert_reconciliation_line(
            recon_id, il["id"], ol["order_line_id"], status, qty_diff, price_diff, rule
        )

    overall    = "MATCHED" if not discrepancies else (
        "PARTIAL_MATCH" if len(discrepancies) < len(invoice_lines) else "MISMATCH"
    )
    confidence    = 1.0 - (len(discrepancies) / max(len(invoice_lines), 1))
    completed_at  = datetime.now(timezone.utc).isoformat()
    latency_ms    = int(
        (datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at))
        .total_seconds() * 1000
    )
    repo.update_reconciliation(recon_id, overall, confidence, completed_at, latency_ms)
    return recon_id, discrepancies


def handle_exceptions(recon_id: int, discrepancies: list):
    """Auto-approve, block, or flag for human review based on rules."""
    for d in discrepancies:
        exc_type    = d.get("type", "UNKNOWN")
        severity    = "CRITICAL" if exc_type == "NO_MATCH" else "WARNING"
        description = (
            f"{exc_type}: product={d.get('product_code')}, "
            f"qty_diff={d.get('qty_diff', 'N/A')}, "
            f"price_diff={d.get('price_diff', 'N/A')}. "
            f"Rule: {d.get('rule', 'N/A')}"
        )
        auto_action = "BLOCKED" if severity == "CRITICAL" else "NEEDS_REVIEW"
        repo.insert_exception(recon_id, exc_type, severity, description, auto_action)
