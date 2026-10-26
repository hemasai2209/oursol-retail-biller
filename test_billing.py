
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from billing import calculate_bill, create_bill


class TestBillingCalculation(unittest.TestCase):

    def setUp(self):
        self.items = [
            {"name": "Product A", "quantity": 2, "unit_price": 100},
            {"name": "Product B", "quantity": 1, "unit_price": 50},
        ]

    def test_correct_bill_calculation(self):
        result = calculate_bill(self.items, discount_percent=10)
        self.assertEqual(result["subtotal"], 250.00)
        self.assertEqual(result["discount_amount"], 25.00)
        self.assertEqual(result["total"], 225.00)

    def test_zero_discount(self):
        result = calculate_bill(self.items, discount_percent=0)
        self.assertEqual(result["subtotal"], 250.00)
        self.assertEqual(result["discount_amount"], 0.00)
        self.assertEqual(result["total"], 250.00)

    def test_empty_items_rejected(self):
        with self.assertRaises(ValueError):
            calculate_bill([], discount_percent=0)

    def test_negative_quantity_rejected(self):
        items = [
            {"name": "Product A", "quantity": -1, "unit_price": 100}
        ]
        with self.assertRaises(ValueError):
            calculate_bill(items, discount_percent=0)

    def test_discount_above_100_rejected(self):
        with self.assertRaises(ValueError):
            calculate_bill(self.items, discount_percent=101)

    def test_negative_discount_rejected(self):
        with self.assertRaises(ValueError):
            calculate_bill(self.items, discount_percent=-1)


class TestCreateBill(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_retail.db"

        # Create an isolated database for testing.
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                PRAGMA foreign_keys = ON;

                CREATE TABLE products (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    unit_price REAL NOT NULL,
                    stock INTEGER NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE bills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_number TEXT NOT NULL UNIQUE,
                    request_id TEXT UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    subtotal REAL NOT NULL,
                    discount_percent REAL NOT NULL,
                    discount_amount REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    payment_method TEXT NOT NULL,
                    payment_status TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'completed',
                    is_demo INTEGER NOT NULL DEFAULT 0,
                    stock_restored INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE bill_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_id INTEGER NOT NULL,
                    product_id INTEGER,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    line_total REAL NOT NULL,
                    FOREIGN KEY (bill_id) REFERENCES bills(id)
                );

                INSERT INTO products
                    (id, name, unit_price, stock, is_active)
                VALUES
                    (1, 'Product A', 100, 20, 1),
                    (2, 'Product B', 50, 30, 1),
                    (3, 'Inactive Product', 75, 5, 0);
            """)
        conn.close()

        self.patcher = patch(
            "billing.get_connection",
            side_effect=self.get_test_connection,
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def get_test_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_test_bill(
        self,
        items=None,
        request_id="test-request-1",
        payment_status="paid",
    ):
        if items is None:
            items = [{"product_id": 1, "quantity": 2}]

        return create_bill(
            items=items,
            discount_percent=0,
            payment_method="Cash",
            payment_status=payment_status,
            request_id=request_id,
        )

    def get_stock(self, product_id):
        with closing(self.get_test_connection()) as conn:
            row = conn.execute(
                "SELECT stock FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()
            return row["stock"]

    def test_successful_bill_deducts_stock(self):
        bill_number = self.create_test_bill()

        self.assertTrue(bill_number.startswith("BILL-"))
        self.assertEqual(self.get_stock(1), 18)

    def test_overselling_is_rejected(self):
        with self.assertRaises(ValueError):
            self.create_test_bill(
                items=[{"product_id": 1, "quantity": 21}]
            )

        self.assertEqual(self.get_stock(1), 20)

        with closing(self.get_test_connection()) as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM bills"
            ).fetchone()["n"]

        self.assertEqual(count, 0)

    def test_inactive_product_is_rejected(self):
        with self.assertRaises(ValueError):
            self.create_test_bill(
                items=[{"product_id": 3, "quantity": 1}]
            )

        self.assertEqual(self.get_stock(3), 5)

    def test_duplicate_request_does_not_create_second_bill(self):
        first = self.create_test_bill(request_id="same-request")
        second = self.create_test_bill(request_id="same-request")

        self.assertEqual(first, second)
        self.assertEqual(self.get_stock(1), 18)

        with closing(self.get_test_connection()) as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM bills"
            ).fetchone()["n"]

        self.assertEqual(count, 1)

    def test_failed_payment_does_not_deduct_stock(self):
        self.create_test_bill(
            request_id="failed-payment-request",
            payment_status="failed",
        )

        self.assertEqual(self.get_stock(1), 20)

    def test_missing_request_id_is_rejected(self):
        with self.assertRaises(ValueError):
            self.create_test_bill(request_id="")

        self.assertEqual(self.get_stock(1), 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
