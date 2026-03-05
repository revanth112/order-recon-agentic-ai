# Vendor Policies

## VEND-001: ABC Supplies
- Requires exact product_code match (no fuzzy matching).
- Invoice currency must be USD.
- All invoices must reference a valid PO number.
- Quantity tolerance: 5% standard.
- Price tolerance: 2% standard.

## VEND-002: XYZ Distributors
- Allows description-based fuzzy matching (80% similarity threshold) when product_code is missing.
- Invoice currency may be USD or EUR (auto-convert at invoice date rate).
- PO number is optional; match by vendor + product_code + date range.
- Quantity tolerance: 5% standard, 10% for bulk items.
- Price tolerance: 5% standard.

## VEND-003: Global Parts Inc
- Product codes must match but are case-insensitive.
- Invoice may have different line ordering than PO; match by product_code only.
- Strict price tolerance: 1% (no exceptions).
- Quantity tolerance: 3%.
- Any mismatch triggers mandatory human review regardless of severity.

## General Vendor Policy
- New vendors (first invoice) always require human approval regardless of match score.
- Vendors with >10% historical mismatch rate should be flagged for audit.
- Template drift (new invoice structure from known vendor) always triggers a WARNING exception.
