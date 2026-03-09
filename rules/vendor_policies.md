# Vendor Policies

## V-001: Acme Supplies Ltd
- Requires exact product_code match (case-insensitive).
- Invoice currency must match PO currency (USD default).
- All invoices must reference a valid PO number.
- Quantity tolerance: ±5% standard; ±10% for SKUs ending in `-BULK`.
- Price tolerance: ±2% standard; ±5% when invoice quantity matches PO quantity exactly (0% qty variance).

## V-002: GlobalTech Components
- Requires exact product_code match (case-insensitive). No fuzzy or description-based matching.
- Invoice currency must match PO currency.
- All invoices must reference a valid PO number.
- Quantity tolerance: ±10% standard; ±10% for bulk SKUs.
- Price tolerance: ±5% standard; ±5% when invoice quantity matches PO quantity exactly.

## V-003: FastParts Inc
- Product codes must match exactly (case-insensitive).
- Strict price tolerance: ±1% (no exceptions).
- Quantity tolerance: ±3%.
- Any mismatch triggers NEEDS_REVIEW regardless of severity.

## V-004: Premier Industrial
- Requires exact product_code match (case-insensitive).
- Quantity tolerance: ±5%.
- Price tolerance: ±5%; ±5% when invoice quantity matches PO quantity exactly.

## V-005: Sunrise Materials
- Requires exact product_code match (case-insensitive).
- Quantity tolerance: ±5%.
- Price tolerance: ±5%; ±5% when invoice quantity matches PO quantity exactly.

## V-006: TechCore Distributors
- Requires exact product_code match (case-insensitive).
- Quantity tolerance: ±5%.
- Price tolerance: ±3%; ±5% when invoice quantity matches PO quantity exactly.

## V-007: Allied Manufacturing
- Requires exact product_code match (case-insensitive).
- Quantity tolerance: ±5%.
- Price tolerance: ±5%; ±5% when invoice quantity matches PO quantity exactly.

## V-008: Pacific Supply Co
- Requires exact product_code match (case-insensitive).
- Quantity tolerance: ±8%.
- Price tolerance: ±5%; ±5% when invoice quantity matches PO quantity exactly.

## V-009: Metro Parts & Equipment
- Requires exact product_code match (case-insensitive).
- Quantity tolerance: ±5%.
- Price tolerance: ±5%; ±5% when invoice quantity matches PO quantity exactly.

## V-010: Consolidated Logistics
- Requires exact product_code match (case-insensitive).
- Quantity tolerance: ±5%.
- Price tolerance: ±4%; ±5% when invoice quantity matches PO quantity exactly.

## General Vendor Policy
- All invoices must reference a valid, open PO number (status OPEN or PARTIALLY_RECEIVED).
- Invoice currency must match PO currency; currency mismatch raises a CRITICAL exception and blocks reconciliation.
- Product codes are matched case-insensitively; no fuzzy or description-based matching is supported.
- Extraction confidence < 0.8 halts auto-processing and flags the invoice as NEEDS_HUMAN_REVIEW.
- Duplicate billing (re-invoicing already-reconciled quantities) raises a CRITICAL / BLOCKED exception.
- Template drift (new invoice structure from a known vendor) triggers a WARNING exception.
- Vendors with > 10% historical mismatch rate should be flagged for audit.
