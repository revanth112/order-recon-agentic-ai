# Order Reconciliation Business Rules & Guidelines

## 1. Overview

This document describes how the multi-agent reconciliation system processes invoices against Purchase Orders (POs).

The pipeline has three agents:
1. **Extractor Agent** — Calls Azure OpenAI GPT-4o to extract structured fields from invoice JSON and validates with Pydantic v2.
2. **Matcher Agent** — Matches invoice lines to open PO lines by `product_code` (case-insensitive exact match), applying per-vendor tolerance rules and querying this RAG index for rule context.
3. **Exception Handler** — Classifies discrepancies (CRITICAL / WARNING / INFO), sets auto-action (BLOCKED / NEEDS_REVIEW / AUTO_APPROVED), and persists results to SQLite.

---

## 2. Match Rules

### 2.1 Quantity Matching (Rule: QTY_TOLERANCE_STANDARD)

- A **±5% variance** in quantity is allowed for standard SKUs.
- A **±10% variance** is allowed for bulk commodity SKUs whose product code ends with `-BULK`.
- Per-vendor quantity tolerances override the global default:
  - V-001 (Acme): ±5% | V-002 (GlobalTech): ±10% | V-003 (FastParts): ±3%
  - V-004 (Premier): ±5% | V-005 (Sunrise): ±5% | V-006 (TechCore): ±5%
  - V-007 (Allied): ±5% | V-008 (Pacific): ±8% | V-009 (Metro): ±5% | V-010 (Consolidated): ±5%
- If variance exceeds the tolerance, classify the line as `OUT_OF_TOLERANCE` → raise `QUANTITY_MISMATCH` (WARNING / NEEDS_REVIEW).

### 2.2 Price Matching (Rule: PRICE_TOLERANCE_STANDARD)

- A **±2% variance** in unit price is the global default.
- A **±5% variance** is allowed when the invoice quantity matches the PO quantity **exactly** (0% quantity variance).
- Per-vendor price tolerances override the global default:
  - V-001 (Acme): ±2% | V-002 (GlobalTech): ±5% | V-003 (FastParts): ±1% (strict)
  - V-004 (Premier): ±5% | V-005 (Sunrise): ±5% | V-006 (TechCore): ±3%
  - V-007 (Allied): ±5% | V-008 (Pacific): ±5% | V-009 (Metro): ±5% | V-010 (Consolidated): ±4%
- If price variance exceeds tolerance, classify as `OUT_OF_TOLERANCE` → raise `PRICE_MISMATCH` (WARNING / NEEDS_REVIEW).
- Price variances are checked after currency validation. Do not compare prices across different currencies.

### 2.3 Product Code Matching (Rule: PRODUCT_CODE_EXACT_MATCH)

- Product codes must match **exactly** between invoice and PO (case-insensitive).
- **No fuzzy matching** or description-based matching is supported.
- If a product code on the invoice has no corresponding line in the resolved PO, classify as `NO_MATCH` → raise a CRITICAL / BLOCKED exception.

---

## 3. Discrepancy Types and Actions

| Discrepancy Type    | Severity | Auto-Action    | Description |
|---------------------|----------|----------------|-------------|
| `INVALID_PO`        | CRITICAL | BLOCKED        | PO number not found or not open for this vendor |
| `DUPLICATE_BILLING` | CRITICAL | BLOCKED        | Invoice qty would exceed already-reconciled qty for this order line |
| `CURRENCY_MISMATCH` | CRITICAL | BLOCKED        | Invoice currency differs from PO currency |
| `NO_MATCH`          | CRITICAL | BLOCKED        | Product code not in the resolved PO |
| `PRICE_MISMATCH`    | WARNING  | NEEDS_REVIEW   | Price variance exceeds vendor tolerance |
| `QUANTITY_MISMATCH` | WARNING  | NEEDS_REVIEW   | Quantity variance exceeds vendor tolerance |
| `TOLERANCE_VARIANCE`| INFO     | AUTO_APPROVED  | Variance within tolerance — auto-approved, audit trail created |

---

## 4. Special Handling

### 4.1 Invalid PO (Rule: NO_MATCH_BLOCK)
If the PO number referenced by the invoice does not exist in the database as an OPEN or PARTIALLY_RECEIVED order for that vendor, the entire invoice is blocked immediately. No reconciliation lines are created. The exception type is `INVALID_PO`, severity CRITICAL, action BLOCKED.

### 4.2 Duplicate Billing
Before matching a line, the system checks how much quantity has already been reconciled against that order line across previous invoices. If `already_reconciled_qty + new_invoice_qty > ordered_qty`, the line is classified as `DUPLICATE_BILLING` (CRITICAL / BLOCKED).

### 4.3 Currency Mismatch (Rule: CURRENCY_CONSISTENCY)
If the invoice currency differs from the PO currency, a `CURRENCY_MISMATCH` exception is raised (CRITICAL / BLOCKED) and overall reconciliation status is forced to MISMATCH. Do not attempt price comparison across different currencies.

### 4.4 Confidence Guardrail (Rule: CONFIDENCE_GUARDRAIL)
If the extractor's confidence score < 0.8, the invoice is flagged as NEEDS_HUMAN_REVIEW and the database is not updated until a human approves.

### 4.5 Auto-Approve (Rule: AUTO_APPROVE_WITHIN_TOLERANCE)
If all invoice lines are MATCHED or WITHIN_TOLERANCE **and** extraction confidence ≥ 0.8, the reconciliation is auto-approved and the database is updated with status COMPLETED.

### 4.6 Partial Match (Rule: PARTIAL_MATCH_REVIEW)
If some lines match and some do not, the overall reconciliation status is set to `PARTIAL_MATCH`. WARNING exceptions are raised for mismatched lines; matched lines can be selectively approved by a human reviewer.

---

## 5. Exception Severity Reference

| Severity | Meaning                                  |
|----------|------------------------------------------|
| CRITICAL | Blocks database update; human must act   |
| WARNING  | Flags for human review; DB may be held   |
| INFO     | Audit trail only; auto-approved          |
