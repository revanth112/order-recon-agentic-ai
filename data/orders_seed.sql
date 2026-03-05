-- orders_seed.sql - Sample seed data for testing
-- Run via: python init_db.py

-- Vendor 1: ABC Supplies (VEND-001)
INSERT OR IGNORE INTO orders (po_number, vendor_id, vendor_name, order_date, status, currency)
VALUES ('PO-001', 'VEND-001', 'ABC Supplies', '2026-02-01', 'OPEN', 'USD');

INSERT OR IGNORE INTO order_lines (order_id, line_number, product_code, description, ordered_qty, unit_price, tax_rate)
VALUES
((SELECT id FROM orders WHERE po_number='PO-001'), 1, 'PROD-123', 'Widget A', 100.0, 10.50, 0.18),
((SELECT id FROM orders WHERE po_number='PO-001'), 2, 'PROD-456', 'Gadget B', 50.0, 25.00, 0.18),
((SELECT id FROM orders WHERE po_number='PO-001'), 3, 'PROD-789', 'Component C', 200.0, 5.75, 0.18);

-- Vendor 2: XYZ Distributors (VEND-002)
INSERT OR IGNORE INTO orders (po_number, vendor_id, vendor_name, order_date, status, currency)
VALUES ('PO-002', 'VEND-002', 'XYZ Distributors', '2026-02-10', 'OPEN', 'USD');

INSERT OR IGNORE INTO order_lines (order_id, line_number, product_code, description, ordered_qty, unit_price, tax_rate)
VALUES
((SELECT id FROM orders WHERE po_number='PO-002'), 1, 'SKU-A01', 'Bearing Set X', 75.0, 18.00, 0.18),
((SELECT id FROM orders WHERE po_number='PO-002'), 2, 'SKU-B02', 'Seal Kit Y', 30.0, 42.50, 0.18);

-- Vendor 3: Global Parts Inc (VEND-003)
INSERT OR IGNORE INTO orders (po_number, vendor_id, vendor_name, order_date, status, currency)
VALUES ('PO-003', 'VEND-003', 'Global Parts Inc', '2026-02-15', 'PARTIALLY_RECEIVED', 'USD');

INSERT OR IGNORE INTO order_lines (order_id, line_number, product_code, description, ordered_qty, unit_price, tax_rate)
VALUES
((SELECT id FROM orders WHERE po_number='PO-003'), 1, 'GP-100', 'Steel Rod 10mm', 500.0, 2.20, 0.18),
((SELECT id FROM orders WHERE po_number='PO-003'), 2, 'GP-200', 'Brass Fitting 1/4"', 150.0, 8.90, 0.18);
