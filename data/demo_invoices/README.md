# Demo Invoice JSONs

This folder contains **15 ready-to-upload invoice JSON files**, one per
reconciliation outcome type.  Upload any file through the
**"Upload & Run Pipeline"** page in the Streamlit UI to see the corresponding
discrepancy appear in the Exceptions Dashboard.

> **Important:** Run `python scripts/seed_data.py` from the project root
> **before** uploading these files.  The seed script creates the matching
> purchase orders (`DEMO-PO-001` … `DEMO-PO-015`) that the pipeline needs to
> reconcile against.  Without that step the invoices will produce `INVALID_PO`
> errors.

---

## File catalogue

| # | File | PO | Vendor | Expected outcome | Exception type | Severity |
|---|------|----|--------|-----------------|----------------|----------|
| 01 | `invoice_01_perfect_match.json` | DEMO-PO-001 | V-001 Acme | ✅ MATCHED | — | — |
| 02 | `invoice_02_within_tolerance.json` | DEMO-PO-002 | V-001 Acme | ✅ MATCHED | TOLERANCE_VARIANCE | INFO / AUTO_APPROVED |
| 03 | `invoice_03_quantity_mismatch.json` | DEMO-PO-003 | V-001 Acme | ⚠️ MISMATCH | QUANTITY_MISMATCH | WARNING / NEEDS_REVIEW |
| 04 | `invoice_04_price_mismatch.json` | DEMO-PO-004 | V-001 Acme | ⚠️ MISMATCH | PRICE_MISMATCH | WARNING / NEEDS_REVIEW |
| 05 | `invoice_05_no_match_sku.json` | DEMO-PO-005 | V-001 Acme | 🚫 MISMATCH | NO_MATCH | CRITICAL / BLOCKED |
| 06 | `invoice_06_invalid_po.json` | DEMO-PO-INVALID | V-001 Acme | 🚫 MISMATCH | INVALID_PO | CRITICAL / BLOCKED |
| 07 | `invoice_07_currency_mismatch.json` | DEMO-PO-007 | V-001 Acme | 🚫 MISMATCH | CURRENCY_MISMATCH | CRITICAL / BLOCKED |
| 08 | `invoice_08_duplicate_billing.json` | DEMO-PO-008 | V-001 Acme | 🚫 MISMATCH | DUPLICATE_BILLING | CRITICAL / BLOCKED |
| 09 | `invoice_09_mixed_discrepancies.json` | DEMO-PO-009 | V-001 Acme | ⚠️ PARTIAL_MATCH | PRICE_MISMATCH + NO_MATCH | WARNING + CRITICAL |
| 10 | `invoice_10_bulk_within_tolerance.json` | DEMO-PO-010 | V-002 GlobalTech | ✅ MATCHED | TOLERANCE_VARIANCE (×2) | INFO / AUTO_APPROVED |
| 11 | `invoice_11_strict_vendor_price_mismatch.json` | DEMO-PO-011 | V-003 FastParts | ⚠️ MISMATCH | PRICE_MISMATCH | WARNING / NEEDS_REVIEW |
| 12 | `invoice_12_multiple_lines_all_matched.json` | DEMO-PO-012 | V-004 Premier | ✅ MATCHED | — | — |
| 13 | `invoice_13_qty_out_of_tolerance.json` | DEMO-PO-013 | V-002 GlobalTech | ⚠️ MISMATCH | QUANTITY_MISMATCH | WARNING / NEEDS_REVIEW |
| 14 | `invoice_14_partial_match.json` | DEMO-PO-014 | V-001 Acme | ⚠️ PARTIAL_MATCH | PRICE_MISMATCH | WARNING / NEEDS_REVIEW |
| 15 | `invoice_15_single_line_matched.json` | DEMO-PO-015 | V-005 Sunrise | ✅ MATCHED | — | — |

---

## Scenario detail

### `01` — Perfect Match
Two lines that exactly match PO qty and price.  The gold-standard happy path.

### `02` — Within Tolerance (auto-approved)
Qty +3 % and price +1.6 % on a V-001 order.  Both fall inside Acme's bands
(qty ±5 %, price ±2 %), so the pipeline auto-approves the variance.

### `03` — Quantity Mismatch
Invoice claims 120 units against an order for 100.  The 20 % overage exceeds
V-001's 5 % qty tolerance → `QUANTITY_MISMATCH`, human review required.

### `04` — Price Mismatch
Unit price is $1.37 vs the ordered $1.25 (+9.6 %).  Exceeds V-001's 2 %
price tolerance with exact quantity → `PRICE_MISMATCH`.

### `05` — No Match SKU
Invoice references `SKU-ZUNK-999` which is not in the PO.  Pipeline cannot
find any order line to match it against → `NO_MATCH`, pipeline blocked.

### `06` — Invalid PO
PO number `DEMO-PO-INVALID` does not exist in the database.  The entire
invoice is immediately blocked → `INVALID_PO`.

### `07` — Currency Mismatch
DEMO-PO-007 was raised in **EUR** but this invoice declares **USD**.  The
currency clash is caught before line-level matching → `CURRENCY_MISMATCH`.

### `08` — Duplicate Billing
DEMO-PO-008 was already fully reconciled (100 × SKU-A100) by a prior invoice
seeded into the DB.  Submitting the same 100 units again exceeds the ordered
qty → `DUPLICATE_BILLING`.

### `09` — Mixed Discrepancies
Line 1 matches exactly.  Line 2 (Flat Washer) has a price 60 % above the
order price → `PRICE_MISMATCH`.  Line 3 references an unknown SKU →
`NO_MATCH`.  Overall: `PARTIAL_MATCH`.

### `10` — Bulk Within Tolerance (V-002 wide bands)
GlobalTech (V-002) allows ±10 % qty and ±5 % price.  Both lines are slightly
off but within those wider bands.  Pipeline auto-approves both →
`TOLERANCE_VARIANCE`.

### `11` — Strict Vendor Price Mismatch (V-003)
FastParts (V-003) enforces a very tight ±1 % price tolerance.  The invoice
price is 3.6 % above the order price, which triggers `PRICE_MISMATCH` even
though the quantity is exact.

### `12` — Multiple Lines, All Matched
Three lines — valves from Premier Industrial (V-004) — all exactly matching.
Tests that the pipeline correctly handles larger matched invoices.

### `13` — Quantity Out of Tolerance (V-002)
GlobalTech allows ±10 % qty variance.  Invoicing 30 units against an order
for 25 is a +20 % overage → `QUANTITY_MISMATCH`.

### `14` — Partial Match
Line 1 matches exactly.  Line 2 (Spring Washer M10) is priced at $1.00 vs
the ordered $0.90 (+11.1 %), well beyond V-001's 2 % limit →
`PRICE_MISMATCH` on one line, overall `PARTIAL_MATCH`.

### `15` — Single Line Matched
The simplest possible invoice: one pump, exact qty and price.  Clean
`MATCHED` result.

---

## Tolerance reference (relevant vendors)

| Vendor | ID | Price tol | Qty tol |
|--------|----|-----------|---------|
| Acme Supplies Ltd | V-001 | ±2 % | ±5 % |
| GlobalTech Components | V-002 | ±5 % | ±10 % |
| FastParts Inc | V-003 | ±1 % | ±3 % |
| Premier Industrial | V-004 | ±5 % | ±5 % |
| Sunrise Materials | V-005 | ±5 % | ±5 % |
