
import sqlite3
import json
import random
from datetime import datetime, timedelta
import os

DB_PATH = "data/order_recon.db"

def generate_dummy_data(n=1000):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    vendors = ["Global Tech Corp", "FastLogistics", "OfficeSupplies Inc", "BuildIt Ltd"]
    products = [
        {"sku": "SKU001", "name": "Laptop", "price": 1200},
        {"sku": "SKU002", "name": "Monitor", "price": 300},
        {"sku": "SKU003", "name": "Keyboard", "price": 50},
        {"sku": "SKU004", "name": "Mouse", "price": 25},
        {"sku": "SKU005", "name": "Desk Chair", "price": 250},
    ]

    print(f"Generating {n} orders and invoices...")

    for i in range(1, n + 1):
        vendor = random.choice(vendors)
        order_date = datetime.now() - timedelta(days=random.randint(1, 30))
        po_id = f"PO-{1000 + i}"
        
        # Insert PO
        cursor.execute(
            "INSERT INTO orders (po_id, vendor_name, total_amount, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (po_id, vendor, 0, "PENDING", order_date.strftime("%Y-%m-%d %H:%M:%S"))
        )

        num_items = random.randint(1, 3)
        total_po_amount = 0
        
        for j in range(num_items):
            prod = random.choice(products)
            qty = random.randint(1, 10)
            price = prod["price"]
            total_po_amount += qty * price
            
            cursor.execute(
                "INSERT INTO order_items (po_id, sku, product_name, quantity, unit_price) VALUES (?, ?, ?, ?, ?)",
                (po_id, prod["sku"], prod["name"], qty, price)
            )

        # Update total amount
        cursor.execute("UPDATE orders SET total_amount = ? WHERE po_id = ?", (total_po_amount, po_id))

        # Generate Invoice JSON
        invoice_id = f"INV-{5000 + i}"
        # Randomly introduce errors (10% chance)
        error_type = random.choices(["none", "price", "qty", "sku"], weights=[80, 7, 7, 6])[0]
        
        invoice_items = []
        # Re-fetch order items for matching
        cursor.execute("SELECT sku, product_name, quantity, unit_price FROM order_items WHERE po_id = ?", (po_id,))
        items = cursor.fetchall()
        
        for sku, name, qty, price in items:
            inv_qty = qty
            inv_price = price
            inv_sku = sku
            
            if error_type == "qty":
                inv_qty += random.randint(1, 5)
            elif error_type == "price":
                inv_price += 10.0
            elif error_type == "sku":
                inv_sku = "WRONG-SKU"

            invoice_items.append({
                "sku": inv_sku,
                "description": name,
                "quantity": inv_qty,
                "unit_price": inv_price
            })

        invoice_data = {
            "invoice_id": invoice_id,
            "po_id": po_id,
            "vendor_name": vendor,
            "items": invoice_items,
            "total_amount": sum(item["quantity"] * item["unit_price"] for item in invoice_items),
            "date": datetime.now().strftime("%Y-%m-%d")
        }

        # Save invoice to a file
        inv_dir = "data/invoices"
        os.makedirs(inv_dir, exist_ok=True)
        with open(f"{inv_dir}/{invoice_id}.json", "w") as f:
            json.dump(invoice_data, f, indent=4)

    conn.commit()
    conn.close()
    print("Dummy data generation complete.")

if __name__ == "__main__":
    generate_dummy_data(1000)
