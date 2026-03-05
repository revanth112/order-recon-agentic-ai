"""
Seed script: inserts ~1000 realistic rows across all tables.
Run from project root:
    python scripts/seed_data.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
import json
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from core.db import init_db, get_connection

random.seed(42)  # reproducible

# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------

VENDORS = [
    ("V-001", "Acme Supplies Ltd"),
    ("V-002", "GlobalTech Components"),
    ("V-003", "FastParts Inc"),
    ("V-004", "Premier Industrial"),
    ("V-005", "Sunrise Materials"),
    ("V-006", "TechCore Distributors"),
    ("V-007", "Allied Manufacturing"),
    ("V-008", "Pacific Supply Co"),
    ("V-009", "Metro Parts & Equipment"),
    ("V-010", "Consolidated Logistics"),
]

# Per-vendor tolerances — must stay in sync with core/config.py VENDOR_TOLERANCES
VENDOR_TOLERANCES = {
    "V-001": {"price_pct": 0.02, "qty_pct": 0.05},
    "V-002": {"price_pct": 0.05, "qty_pct": 0.10},
    "V-003": {"price_pct": 0.01, "qty_pct": 0.03},
    "V-004": {"price_pct": 0.05, "qty_pct": 0.05},
    "V-005": {"price_pct": 0.05, "qty_pct": 0.05},
    "V-006": {"price_pct": 0.03, "qty_pct": 0.05},
    "V-007": {"price_pct": 0.05, "qty_pct": 0.05},
    "V-008": {"price_pct": 0.05, "qty_pct": 0.08},
    "V-009": {"price_pct": 0.05, "qty_pct": 0.05},
    "V-010": {"price_pct": 0.04, "qty_pct": 0.05},
}
DEFAULT_PRICE_TOL = 0.05
DEFAULT_QTY_TOL   = 0.05

# Mix of currencies assigned to orders — 80% USD, 10% EUR, 10% GBP.
# This allows the seed to produce realistic CURRENCY_MISMATCH scenarios.
ORDER_CURRENCY_POOL = ["USD"] * 8 + ["EUR", "GBP"]

# 5 SKUs per vendor (50 total)
VENDOR_PRODUCTS = {
    "V-001": [
        ("SKU-A100", "Hex Bolt M8x20",          1.25),
        ("SKU-A101", "Flat Washer M8",           0.50),
        ("SKU-A102", "Hex Nut M8",               0.75),
        ("SKU-A103", "Self-Tapping Screw 4x16",  0.60),
        ("SKU-A104", "Spring Washer M10",         0.90),
    ],
    "V-002": [
        ("SKU-B100", "CAT5e Ethernet Cable 5m",  8.50),
        ("SKU-B101", "USB-C Cable 2m",           6.75),
        ("SKU-B102", "HDMI Cable 3m",            9.99),
        ("SKU-B103", "Fibre Patch Lead 1m",     14.50),
        ("SKU-B104", "RJ45 Connector Pack/50",   7.25),
    ],
    "V-003": [
        ("SKU-C100", "Pressure Sensor 0-10 bar", 42.00),
        ("SKU-C101", "Temperature Sensor PT100",  38.50),
        ("SKU-C102", "Flow Sensor DN15",         110.00),
        ("SKU-C103", "Proximity Sensor 5mm",      29.75),
        ("SKU-C104", "Vibration Sensor MEMS",     65.00),
    ],
    "V-004": [
        ("SKU-D100", "Ball Valve 1/2\" BSP",     18.50),
        ("SKU-D101", "Gate Valve DN25",           24.00),
        ("SKU-D102", "Check Valve DN20",          19.99),
        ("SKU-D103", "Solenoid Valve 24V",        45.00),
        ("SKU-D104", "Pressure Relief Valve",     55.00),
    ],
    "V-005": [
        ("SKU-E100", "Centrifugal Pump 0.5kW",  185.00),
        ("SKU-E101", "Diaphragm Pump 12V",        95.00),
        ("SKU-E102", "Gear Pump 24V",            125.00),
        ("SKU-E103", "Submersible Pump 1kW",     220.00),
        ("SKU-E104", "Peristaltic Pump Head",     78.00),
    ],
    "V-006": [
        ("SKU-F100", "M12 Connector 4-pin Male",   4.50),
        ("SKU-F101", "M12 Connector 4-pin Female", 4.75),
        ("SKU-F102", "DIN Rail Terminal 4mm",       1.10),
        ("SKU-F103", "Cable Gland PG9",             0.85),
        ("SKU-F104", "Junction Box IP65 100x100",  12.50),
    ],
    "V-007": [
        ("SKU-G100", "Oil Filter 10 Micron",      14.00),
        ("SKU-G101", "Air Filter G4 Panel",        8.50),
        ("SKU-G102", "Water Filter Cartridge 5μm", 6.75),
        ("SKU-G103", "Hydraulic Filter Element",   32.00),
        ("SKU-G104", "HEPA Filter H13",            48.00),
    ],
    "V-008": [
        ("SKU-H100", "Steel Bracket L-Shape 50mm",  2.20),
        ("SKU-H101", "Aluminium Channel 1m",        9.80),
        ("SKU-H102", "Unistrut P1000 3m",          22.50),
        ("SKU-H103", "Cable Tray 150x50 3m",       18.75),
        ("SKU-H104", "Din Rail 35mm 1m",            3.60),
    ],
    "V-009": [
        ("SKU-I100", "Circuit Breaker 16A 1P",     12.00),
        ("SKU-I101", "Fuse 10A 5x20mm Pack/10",     3.50),
        ("SKU-I102", "Contactor 25A 24V coil",     38.00),
        ("SKU-I103", "Relay 24VDC SPDT",            8.25),
        ("SKU-I104", "MCB 32A 3P Type C",          28.50),
    ],
    "V-010": [
        ("SKU-J100", "Pallet Wrap 500m Roll",      22.00),
        ("SKU-J101", "Stretch Film 300mm",         14.50),
        ("SKU-J102", "Bubble Wrap 50m Roll",       18.00),
        ("SKU-J103", "Cardboard Box 400x300x200",   1.80),
        ("SKU-J104", "Tape Gun Dispenser",          6.50),
    ],
}

NOW = datetime.now(timezone.utc)


def rand_dt(days_back_max: int, days_back_min: int = 0) -> str:
    """Return a random ISO-format datetime string within the past N days."""
    delta = timedelta(days=random.randint(days_back_min, days_back_max),
                      hours=random.randint(0, 23),
                      minutes=random.randint(0, 59))
    return (NOW - delta).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Seeding functions
# ---------------------------------------------------------------------------

def seed_orders_and_lines(conn):
    """Insert 200 orders + ~700 order_lines."""
    order_ids = []       # list of (order_id, vendor_id, po_number, currency)
    order_line_ids = []  # list of (order_line_id, order_id, product_code, qty, price, tax)

    for i in range(1, 201):
        vendor_id, vendor_name = random.choice(VENDORS)
        po_number = f"PO-{2024_0000 + i:06d}"
        order_date = rand_dt(365, 30)
        status = random.choices(
            ["OPEN", "PARTIALLY_RECEIVED", "CLOSED"],
            weights=[60, 25, 15]
        )[0]
        currency = random.choice(ORDER_CURRENCY_POOL)

        conn.execute(
            """INSERT OR IGNORE INTO orders
               (po_number, vendor_id, vendor_name, order_date, status, currency)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (po_number, vendor_id, vendor_name, order_date, status, currency),
        )
        order_id = conn.execute(
            "SELECT id FROM orders WHERE po_number = ?", (po_number,)
        ).fetchone()[0]

        products = VENDOR_PRODUCTS[vendor_id]
        num_lines = random.randint(2, 5)
        chosen = random.sample(products, min(num_lines, len(products)))

        for ln, (sku, desc, base_price) in enumerate(chosen, start=1):
            qty = round(random.uniform(5, 200), 2)
            price = round(base_price * random.uniform(0.95, 1.05), 4)
            tax = round(random.choice([0.0, 0.05, 0.10, 0.20]), 2)

            conn.execute(
                """INSERT INTO order_lines
                   (order_id, line_number, product_code, description,
                    ordered_qty, unit_price, tax_rate)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (order_id, ln, sku, desc, qty, price, tax),
            )
            ol_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            order_line_ids.append((ol_id, order_id, sku, qty, price, tax))

        order_ids.append((order_id, vendor_id, po_number, currency))

    return order_ids, order_line_ids


def seed_invoices_and_lines(conn, order_ids, order_line_ids):
    """Insert 200 invoices + matching invoice_lines with realistic variances."""
    # Build a lookup: order_id -> list of order_line rows
    ol_by_order = {}
    for ol_id, order_id, sku, qty, price, tax in order_line_ids:
        ol_by_order.setdefault(order_id, []).append(
            (ol_id, sku, qty, price, tax)
        )

    invoice_records = []  # (invoice_id, vendor_id, po_number, invoice_currency, order_currency)
    inv_line_records = []  # (inv_line_id, invoice_id, order_line_id, inv_sku, ord_sku,
                           #  inv_qty, ord_qty, inv_price, ord_price, category)

    # Build a vendor -> all products lookup for NO_MATCH lines
    all_skus_by_vendor = {
        vid: [row[0] for row in prods]
        for vid, prods in VENDOR_PRODUCTS.items()
    }

    for idx, (order_id, vendor_id, po_number, order_currency) in enumerate(order_ids, start=1):
        inv_number = f"INV-{2024_0000 + idx:06d}"
        inv_date = rand_dt(30, 1)
        extraction_conf = round(random.uniform(0.70, 1.00), 4)
        template_hash = hashlib.md5(vendor_id.encode()).hexdigest()
        vendor_name = next(n for v, n in VENDORS if v == vendor_id)

        # For non-USD orders, 40% chance the invoice arrives in the wrong currency
        # (simulates CURRENCY_MISMATCH). USD orders always match.
        if order_currency != "USD" and random.random() < 0.40:
            invoice_currency = "USD"   # deliberate mismatch
        else:
            invoice_currency = order_currency

        raw_payload = {
            "invoice_number": inv_number,
            "po_number": po_number,
            "vendor_id": vendor_id,
            "currency": invoice_currency,
        }

        conn.execute(
            """INSERT INTO invoices
               (invoice_number, vendor_id, vendor_name, invoice_date,
                currency, raw_json, extraction_confidence, template_hash, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PROCESSED')""",
            (inv_number, vendor_id, vendor_name, inv_date,
             invoice_currency, json.dumps(raw_payload), extraction_conf, template_hash),
        )
        invoice_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        invoice_records.append((invoice_id, vendor_id, po_number, invoice_currency, order_currency))

        order_lines = ol_by_order.get(order_id, [])
        num_lines = random.randint(2, min(5, len(order_lines))) if order_lines else 0
        chosen_lines = random.sample(order_lines, num_lines) if order_lines else []

        # Per-vendor tolerance bounds for WITHIN_TOLERANCE generation
        vtols = VENDOR_TOLERANCES.get(vendor_id, {})
        p_tol = vtols.get("price_pct", DEFAULT_PRICE_TOL)
        q_tol = vtols.get("qty_pct",   DEFAULT_QTY_TOL)

        for ln_num, (ol_id, sku, o_qty, o_price, o_tax) in enumerate(chosen_lines, start=1):
            # Determine match category
            category = random.choices(
                ["MATCHED", "WITHIN_TOLERANCE", "OUT_OF_TOLERANCE", "NO_MATCH", "DUPLICATE_BILLING"],
                weights=[55, 20, 15, 5, 5]
            )[0]

            if category == "MATCHED":
                inv_qty   = o_qty
                inv_price = o_price
                inv_sku   = sku
            elif category == "WITHIN_TOLERANCE":
                # Stay inside per-vendor tolerance band (use 90% of the band to be safe)
                qty_band   = q_tol * 0.90
                price_band = p_tol * 0.90
                inv_qty   = round(o_qty   * random.uniform(1 - qty_band,   1 + qty_band),   2)
                inv_price = round(o_price * random.uniform(1 - price_band, 1 + price_band), 4)
                inv_sku   = sku
            elif category == "OUT_OF_TOLERANCE":
                # Exceed the tolerance band noticeably (>= 20% outside each respective limit)
                inv_qty   = round(o_qty   * random.uniform(1 + q_tol * 1.2, 1 + q_tol * 3.0), 2)
                inv_price = round(o_price * random.uniform(1 + p_tol * 1.2, 1 + p_tol * 3.0), 4)
                inv_sku   = sku
            elif category == "DUPLICATE_BILLING":
                # Same quantities/prices as the order — simulates a duplicate submission
                inv_qty   = o_qty
                inv_price = o_price
                inv_sku   = sku
            else:  # NO_MATCH
                vendor_skus = all_skus_by_vendor.get(vendor_id, [])
                other_skus  = [s for s in vendor_skus if s != sku]
                inv_sku   = random.choice(other_skus) if other_skus else f"UNKNOWN-{random.randint(100, 999)}"
                inv_qty   = o_qty
                inv_price = o_price

            inv_tax = o_tax if category != "OUT_OF_TOLERANCE" else round(
                random.choice([0.0, 0.05, 0.10, 0.20]), 2
            )

            conn.execute(
                """INSERT INTO invoice_lines
                   (invoice_id, line_number, product_code, description,
                    quantity, unit_price, tax_rate)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (invoice_id, ln_num, inv_sku,
                 next((d for s, d, _ in VENDOR_PRODUCTS[vendor_id] if s == inv_sku),
                      "Unknown Product"),
                 inv_qty, inv_price, inv_tax),
            )
            inv_line_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            inv_line_records.append(
                (inv_line_id, invoice_id, ol_id, inv_sku, sku,
                 inv_qty, o_qty, inv_price, o_price, category)
            )

    return invoice_records, inv_line_records


def seed_reconciliations(conn, invoice_records, inv_line_records):
    """Insert 200 reconciliations + reconciliation_lines + exceptions.

    Exception types, severities and auto_actions match the new matcher logic:
      NO_MATCH / DUPLICATE_BILLING / CURRENCY_MISMATCH / INVALID_PO → CRITICAL / BLOCKED
      QUANTITY_MISMATCH / PRICE_MISMATCH                              → WARNING  / NEEDS_REVIEW
      TOLERANCE_VARIANCE                                              → INFO     / AUTO_APPROVED
    """
    # Group invoice lines by invoice_id
    lines_by_invoice = {}
    for row in inv_line_records:
        inv_line_id, invoice_id = row[0], row[1]
        lines_by_invoice.setdefault(invoice_id, []).append(row)

    recon_ids = {}  # invoice_id -> recon_id
    exception_count = 0
    recon_line_count = 0

    for invoice_id, vendor_id, po_number, invoice_currency, order_currency in invoice_records:
        lines = lines_by_invoice.get(invoice_id, [])
        categories = [row[9] for row in lines]
        has_currency_mismatch = invoice_currency != order_currency

        # Determine overall_status from line categories and currency state
        if has_currency_mismatch:
            # Currency mismatch always forces MISMATCH regardless of line results
            overall_status = "MISMATCH"
            confidence = round(random.uniform(0.10, 0.40), 4)
        elif all(c in ("MATCHED", "WITHIN_TOLERANCE") for c in categories):
            # WITHIN_TOLERANCE lines are within acceptable variance — treated as matched
            overall_status = "MATCHED"
            confidence = round(random.uniform(0.90, 1.00), 4)
        elif any(c in ("OUT_OF_TOLERANCE", "NO_MATCH", "DUPLICATE_BILLING") for c in categories):
            overall_status = random.choices(
                ["MISMATCH", "PARTIAL_MATCH"], weights=[60, 40]
            )[0]
            confidence = round(random.uniform(0.50, 0.79), 4)
        else:
            overall_status = random.choices(
                ["MATCHED", "PARTIAL_MATCH"], weights=[40, 60]
            )[0]
            confidence = round(random.uniform(0.75, 0.95), 4)

        started = rand_dt(30, 1)
        latency = random.randint(500, 8000)
        completed_dt = (
            datetime.strptime(started, "%Y-%m-%d %H:%M:%S")
            + timedelta(milliseconds=latency)
        ).strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            """INSERT INTO reconciliations
               (invoice_id, po_number, overall_status, reconciliation_confidence,
                started_at, completed_at, latency_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (invoice_id, po_number, overall_status, confidence,
             started, completed_dt, latency),
        )
        recon_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        recon_ids[invoice_id] = recon_id

        # ── Invoice-level exception: CURRENCY_MISMATCH ────────────────────────
        if has_currency_mismatch:
            desc = (
                f"CURRENCY_MISMATCH: invoice currency '{invoice_currency}' "
                f"does not match order currency '{order_currency}' for PO {po_number}"
            )
            resolved = random.choices([0, 1], weights=[80, 20])[0]
            resolved_at = rand_dt(10, 1) if resolved else None
            resolved_by = (
                random.choice(["alice@example.com", "bob@example.com", "carol@example.com"])
                if resolved else None
            )
            conn.execute(
                """INSERT INTO exceptions
                   (reconciliation_id, type, severity, description,
                    auto_action, resolved, resolved_by, resolved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (recon_id, "CURRENCY_MISMATCH", "CRITICAL", desc,
                 "BLOCKED", resolved, resolved_by, resolved_at),
            )
            exception_count += 1

        # ── Per-line reconciliation records and exceptions ────────────────────
        for row in lines:
            (inv_line_id, _inv_id, ol_id, inv_sku, ord_sku,
             inv_qty, ord_qty, inv_price, ord_price, category) = row

            qty_diff   = round(inv_qty   - ord_qty,   4)
            price_diff = round(inv_price - ord_price, 4)

            # Map category to match_status stored in reconciliation_lines
            match_status = category  # MATCHED / WITHIN_TOLERANCE / OUT_OF_TOLERANCE /
                                     # NO_MATCH / DUPLICATE_BILLING

            applied_rule = {
                "MATCHED":            "Exact match",
                "WITHIN_TOLERANCE":   f"Within vendor tolerance ({vendor_id})",
                "OUT_OF_TOLERANCE":   "No matching rule found. Flag for manual review.",
                "NO_MATCH":           "No matching rule found. Flag for manual review.",
                "DUPLICATE_BILLING":  "No matching rule found. Flag for manual review.",
            }[category]

            conn.execute(
                """INSERT INTO reconciliation_lines
                   (reconciliation_id, invoice_line_id, order_line_id,
                    match_status, quantity_diff, price_diff, applied_rule)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (recon_id, inv_line_id, ol_id,
                 match_status, qty_diff, price_diff, applied_rule),
            )
            recon_line_count += 1

            # ── Per-line exceptions (aligned with new handle_exceptions logic) ──
            if category == "NO_MATCH":
                exc_type  = "NO_MATCH"
                severity  = "CRITICAL"
                desc = (f"NO_MATCH: product={inv_sku}, PO has {ord_sku}. "
                        f"No matching rule found. Flag for manual review.")
                auto_action = "BLOCKED"

            elif category == "DUPLICATE_BILLING":
                exc_type  = "DUPLICATE_BILLING"
                severity  = "CRITICAL"
                desc = (f"DUPLICATE_BILLING: product={inv_sku}, "
                        f"invoice_qty={inv_qty}, ordered_qty={ord_qty}. "
                        f"No matching rule found. Flag for manual review.")
                auto_action = "BLOCKED"

            elif category == "OUT_OF_TOLERANCE":
                qty_pct   = abs(qty_diff / ord_qty)     if ord_qty   else 0
                price_pct = abs(price_diff / ord_price) if ord_price else 0
                vtols     = VENDOR_TOLERANCES.get(vendor_id, {})
                q_tol     = vtols.get("qty_pct",   DEFAULT_QTY_TOL)
                p_tol     = vtols.get("price_pct", DEFAULT_PRICE_TOL)
                if qty_pct > q_tol:
                    exc_type = "QUANTITY_MISMATCH"
                    desc = (f"QUANTITY_MISMATCH: product={inv_sku}, "
                            f"qty_diff={qty_diff:+.2f} ({qty_pct:.1%} variance, "
                            f"vendor tolerance {q_tol:.2%})")
                else:
                    exc_type = "PRICE_MISMATCH"
                    desc = (f"PRICE_MISMATCH: product={inv_sku}, "
                            f"price_diff={price_diff:+.4f} ({price_pct:.1%} variance, "
                            f"vendor tolerance {p_tol:.2%})")
                severity    = "WARNING"
                auto_action = "NEEDS_REVIEW"

            elif category == "WITHIN_TOLERANCE":
                exc_type  = "TOLERANCE_VARIANCE"
                severity  = "INFO"
                vtols     = VENDOR_TOLERANCES.get(vendor_id, {})
                q_tol     = vtols.get("qty_pct",   DEFAULT_QTY_TOL)
                p_tol     = vtols.get("price_pct", DEFAULT_PRICE_TOL)
                desc = (f"TOLERANCE_VARIANCE: product={inv_sku}, "
                        f"qty_diff={qty_diff:+.2f}, price_diff={price_diff:+.4f}. "
                        f"Within vendor tolerance (qty={q_tol:.2%}, price={p_tol:.2%}).")
                auto_action = "AUTO_APPROVED"

            else:
                # MATCHED lines do not generate exceptions
                continue

            resolved = random.choices([0, 1], weights=[70, 30])[0]
            resolved_at = rand_dt(10, 1) if resolved else None
            resolved_by = (
                random.choice(["alice@example.com", "bob@example.com",
                               "carol@example.com"])
                if resolved else None
            )

            conn.execute(
                """INSERT INTO exceptions
                   (reconciliation_id, type, severity, description,
                    auto_action, resolved, resolved_by, resolved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (recon_id, exc_type, severity, desc,
                 auto_action, resolved, resolved_by, resolved_at),
            )
            exception_count += 1

    return recon_ids, recon_line_count, exception_count


def seed_invoice_templates(conn):
    """Insert 10 invoice_templates — one per vendor."""
    for vendor_id, vendor_name in VENDORS:
        tmpl_hash = hashlib.md5(f"template-{vendor_id}".encode()).hexdigest()
        first_seen = rand_dt(365, 180)
        last_seen = rand_dt(30, 1)
        notes = f"Standard {vendor_name} invoice layout"
        conn.execute(
            """INSERT OR IGNORE INTO invoice_templates
               (vendor_id, template_hash, first_seen_at, last_seen_at,
                is_active, notes)
               VALUES (?, ?, ?, ?, 1, ?)""",
            (vendor_id, tmpl_hash, first_seen, last_seen, notes),
        )


def seed_metrics_runs(conn):
    """Insert 50 historical metrics_runs over the last 6 months."""
    for i in range(50):
        run_ts = rand_dt(180, i * 3)
        invoices_processed = random.randint(5, 40)
        mismatch_rate = round(random.uniform(0.05, 0.35), 4)
        avg_conf = round(random.uniform(0.75, 0.98), 4)
        avg_latency = round(random.uniform(800, 5000), 1)
        conn.execute(
            """INSERT INTO metrics_runs
               (run_timestamp, invoices_processed, mismatch_rate,
                avg_extraction_confidence, avg_reconciliation_latency_ms)
               VALUES (?, ?, ?, ?, ?)""",
            (run_ts, invoices_processed, mismatch_rate, avg_conf, avg_latency),
        )


def seed_pipeline_logs(conn, invoice_records, recon_ids):
    """Insert EXTRACTOR + MATCHER + EXCEPTION_HANDLER logs per invoice."""
    log_count = 0
    for invoice_id, vendor_id, po_number, invoice_currency, order_currency in invoice_records:
        run_id = str(uuid.UUID(int=random.getrandbits(128)))
        recon_id = recon_ids.get(invoice_id, "N/A")
        base_ts = datetime.strptime(rand_dt(30, 1), "%Y-%m-%d %H:%M:%S")
        has_currency_mismatch = invoice_currency != order_currency

        log_entries = [
            (
                "EXTRACTOR", "INFO",
                f"[EXTRACTOR] Starting extraction for invoice_id={invoice_id} vendor={vendor_id}",
                base_ts,
            ),
            (
                "EXTRACTOR", "INFO",
                f"[EXTRACTOR] Template matched. hash={hashlib.md5(vendor_id.encode()).hexdigest()[:8]}",
                base_ts + timedelta(milliseconds=random.randint(100, 600)),
            ),
            (
                "EXTRACTOR", "INFO",
                f"[EXTRACTOR] Done. invoice_number extracted, confidence={round(random.uniform(0.70, 1.00), 3)}",
                base_ts + timedelta(milliseconds=random.randint(600, 1500)),
            ),
            (
                "MATCHER", "INFO",
                f"[MATCHER] Starting order matching...",
                base_ts + timedelta(milliseconds=random.randint(1500, 2200)),
            ),
        ]

        # Add a WARNING log when currency mismatches
        if has_currency_mismatch:
            log_entries.append((
                "MATCHER", "WARNING",
                f"[MATCHER] WARNING: Currency mismatch detected — "
                f"invoice='{invoice_currency}', order='{order_currency}' for PO '{po_number}'",
                base_ts + timedelta(milliseconds=random.randint(2200, 2800)),
            ))

        log_entries += [
            (
                "MATCHER", "INFO",
                f"[MATCHER] Done. recon_id={recon_id}",
                base_ts + timedelta(milliseconds=random.randint(2800, 4500)),
            ),
            (
                "EXCEPTION_HANDLER", "INFO",
                f"[EXCEPTION_HANDLER] Processing discrepancies...",
                base_ts + timedelta(milliseconds=random.randint(4500, 5500)),
            ),
            (
                "EXCEPTION_HANDLER", "INFO",
                f"[EXCEPTION_HANDLER] Done. Final status=COMPLETED",
                base_ts + timedelta(milliseconds=random.randint(5500, 7000)),
            ),
        ]

        for agent, level, message, ts in log_entries:
            conn.execute(
                """INSERT INTO pipeline_logs
                   (invoice_id, run_id, agent, level, message, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (invoice_id, run_id, agent, level, message,
                 ts.strftime("%Y-%m-%d %H:%M:%S")),
            )
            log_count += 1

    return log_count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def count_rows(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def clear_tables(conn):
    """Delete all seeded rows so the script is safe to re-run."""
    # Delete in reverse FK order to avoid constraint violations
    tables = [
        "pipeline_logs", "metrics_runs", "invoice_templates",
        "exceptions", "reconciliation_lines", "reconciliations",
        "invoice_lines", "invoices", "order_lines", "orders",
    ]
    for table in tables:
        conn.execute(f"DELETE FROM {table}")


def main():
    init_db()

    with get_connection() as conn:
        print("Clearing existing seed data …")
        clear_tables(conn)

        print("Seeding orders and order_lines …")
        order_ids, order_line_ids = seed_orders_and_lines(conn)

        print("Seeding invoices and invoice_lines …")
        invoice_records, inv_line_records = seed_invoices_and_lines(
            conn, order_ids, order_line_ids
        )

        print("Seeding reconciliations, reconciliation_lines, exceptions …")
        recon_ids, recon_line_count, exception_count = seed_reconciliations(
            conn, invoice_records, inv_line_records
        )

        print("Seeding invoice_templates …")
        seed_invoice_templates(conn)

        print("Seeding metrics_runs …")
        seed_metrics_runs(conn)

        print("Seeding pipeline_logs …")
        log_count = seed_pipeline_logs(conn, invoice_records, recon_ids)

    # Summary
    with get_connection() as conn:
        tables = [
            "orders", "order_lines", "invoices", "invoice_lines",
            "reconciliations", "reconciliation_lines", "exceptions",
            "invoice_templates", "metrics_runs", "pipeline_logs",
        ]
        totals = {t: count_rows(conn, t) for t in tables}

    total_rows = sum(totals.values())
    print(
        f"\n✅ Seeded {totals['orders']} orders, "
        f"{totals['order_lines']} order_lines, "
        f"{totals['invoices']} invoices, "
        f"{totals['invoice_lines']} invoice_lines, "
        f"{totals['reconciliations']} reconciliations, "
        f"{totals['reconciliation_lines']} reconciliation_lines, "
        f"{totals['exceptions']} exceptions, "
        f"{totals['invoice_templates']} invoice_templates, "
        f"{totals['metrics_runs']} metrics_runs, "
        f"{totals['pipeline_logs']} pipeline_logs"
    )
    print("\nRow counts per table:")
    for table, cnt in totals.items():
        print(f"  {table:<30} {cnt:>5}")
    print(f"\n  {'TOTAL':<30} {total_rows:>5}")


if __name__ == "__main__":
    main()
