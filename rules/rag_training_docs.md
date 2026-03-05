# Order Reconciliation Business Rules & Guidelines

## 1. Overview
This document outlines the standard operating procedures for reconciling invoices against purchase orders (POs) and delivery records.

## 2. Match Rules
### 2.1 Quantity Matching
- Invoiced quantity must exactly match the PO quantity.
- If quantity matches but is less than the delivery record, it is acceptable (partial delivery).
- If quantity is more than PO, it must be flagged as "Quantity Mismatch".

### 2.2 Price Matching
- Unit price must match the PO unit price.
- Total amount (Qty * Price) must match the sum of line items.
- Tax calculations should follow regional standards (standard 10% for simulation).

### 2.3 Product Codes
- SKU/Product codes must be an exact string match.
- Description mismatches are acceptable if SKU matches, but should be noted.

## 3. Discrepancy Handling
### 3.1 Price Mismatch
- If invoice price > PO price, the invoice is rejected for manual review.
- If invoice price < PO price, the invoice can be auto-approved, but a "Price Variance" flag is raised.

### 3.2 Missing PO
- If an invoice references a PO ID that does not exist in the database, the agent should move it to the "Exception" state immediately.

### 3.3 Duplicate Invoices
- Invoices with the same Invoice ID and Vendor ID should be rejected as duplicates.

## 4. Vendor Specific Policies
- **Global Tech Corp**: Allows 2% price variance without manual approval.
- **FastLogistics**: Requires matching delivery record ID for all line items.
