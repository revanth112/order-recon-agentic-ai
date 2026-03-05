# Reconciliation Rules

## Rule 1: Quantity Tolerance
- **Name**: QTY_TOLERANCE_STANDARD
- A 5% variance in quantity is allowed for all standard products.
- A 10% variance is allowed for bulk commodity SKUs (suffix `-BULK`).
- If variance exceeds tolerance, classify as `OUT_OF_TOLERANCE` and raise an exception.

## Rule 2: Price Tolerance
- **Name**: PRICE_TOLERANCE_STANDARD
- A 2% variance in unit price is allowed for all products.
- A 5% variance in unit price is allowed when the quantity matches exactly (0% variance).
- Price variances are checked after currency normalization.

## Rule 3: Product Code Matching
- **Name**: PRODUCT_CODE_EXACT_MATCH
- Product codes must match exactly (case-insensitive) between invoice and PO.
- If a product code on the invoice has no match in any open PO for that vendor, classify as `NO_MATCH`.

## Rule 4: No Match Handling
- **Name**: NO_MATCH_BLOCK
- If a product code appears on the invoice but has no corresponding order line, **block** the auto-update.
- Always raise a `CRITICAL` exception and require human review before any DB update.

## Rule 5: Currency
- **Name**: CURRENCY_CONSISTENCY
- Invoice currency must match PO currency. If they differ, raise a `CRITICAL` exception.
- Do not attempt price comparison across different currencies.

## Rule 6: Confidence Threshold
- **Name**: CONFIDENCE_GUARDRAIL
- If extraction confidence < 0.8, halt auto-processing and flag invoice as `NEEDS_HUMAN_REVIEW`.
- Do not update the database until a human approves the extraction output.

## Rule 7: Auto-Approve
- **Name**: AUTO_APPROVE_WITHIN_TOLERANCE
- If all line items are `MATCHED` or `WITHIN_TOLERANCE` and confidence >= 0.8, auto-approve and update DB.
- Log the reconciliation result with status `COMPLETED`.

## Rule 8: Partial Match
- **Name**: PARTIAL_MATCH_REVIEW
- If some lines match and some do not, set overall status to `PARTIAL_MATCH`.
- Raise `WARNING` exceptions for mismatched lines.
- Allow human to selectively approve matched lines.
