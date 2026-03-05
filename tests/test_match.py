# tests/test_match.py - Unit tests for the Matcher agent and tolerance logic
import pytest


def test_qty_within_tolerance():
    """Quantities within 5% should be WITHIN_TOLERANCE."""
    from core.config import QTY_TOLERANCE_PCT
    ordered_qty = 100.0
    invoice_qty = 97.0
    qty_pct = abs(invoice_qty - ordered_qty) / ordered_qty
    assert qty_pct <= QTY_TOLERANCE_PCT, f"Expected within tolerance: {qty_pct:.2%}"


def test_qty_out_of_tolerance():
    """Quantities exceeding 5% should be OUT_OF_TOLERANCE."""
    from core.config import QTY_TOLERANCE_PCT
    ordered_qty = 100.0
    invoice_qty = 80.0
    qty_pct = abs(invoice_qty - ordered_qty) / ordered_qty
    assert qty_pct > QTY_TOLERANCE_PCT, f"Expected out of tolerance: {qty_pct:.2%}"


def test_price_within_tolerance():
    """Prices within 5% should be WITHIN_TOLERANCE."""
    from core.config import PRICE_TOLERANCE_PCT
    order_price = 10.50
    invoice_price = 10.80
    price_pct = abs(invoice_price - order_price) / order_price
    assert price_pct <= PRICE_TOLERANCE_PCT, f"Expected within tolerance: {price_pct:.2%}"


def test_price_out_of_tolerance():
    """Prices exceeding 5% should be OUT_OF_TOLERANCE."""
    from core.config import PRICE_TOLERANCE_PCT
    order_price = 10.50
    invoice_price = 12.00
    price_pct = abs(invoice_price - order_price) / order_price
    assert price_pct > PRICE_TOLERANCE_PCT, f"Expected out of tolerance: {price_pct:.2%}"


# TODO: Add integration tests for run_matcher with mocked DB and LLM
