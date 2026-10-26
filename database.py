
import sqlite3
from pathlib import Path

# Database file is created inside the project folder.
DB_PATH = Path(__file__).resolve().parent / "retail.db"


def get_connection():
    """Open a database connection with foreign-key checks enabled."""
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    """Create the required tables and insert the initial products."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                unit_price REAL NOT NULL CHECK (unit_price > 0),
                stock INTEGER NOT NULL CHECK (stock >= 0),
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_number TEXT NOT NULL UNIQUE,
                request_id TEXT UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                subtotal REAL NOT NULL CHECK (subtotal >= 0),
                discount_percent REAL NOT NULL
                    CHECK (discount_percent BETWEEN 0 AND 100),
                discount_amount REAL NOT NULL CHECK (discount_amount >= 0),
                total_amount REAL NOT NULL CHECK (total_amount >= 0),
                payment_method TEXT NOT NULL,
                payment_status TEXT NOT NULL
                    CHECK (payment_status IN
                        ('paid', 'pending', 'failed', 'refunded')),
                status TEXT NOT NULL DEFAULT 'completed'
                    CHECK (status IN ('completed', 'cancelled')),
                is_demo INTEGER NOT NULL DEFAULT 0
                    CHECK (is_demo IN (0, 1)),
                stock_restored INTEGER NOT NULL DEFAULT 0
                    CHECK (stock_restored IN (0, 1))
            );

            CREATE TABLE IF NOT EXISTS bill_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price REAL NOT NULL CHECK (unit_price > 0),
                line_total REAL NOT NULL CHECK (line_total >= 0),
                FOREIGN KEY (bill_id) REFERENCES bills(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
                    ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_bills_created_at
                ON bills(created_at);

            CREATE INDEX IF NOT EXISTS idx_bills_status
                ON bills(status);

            CREATE INDEX IF NOT EXISTS idx_bill_items_product
                ON bill_items(product_id);
        """)

        seed_products(conn)


def seed_products(conn):
    """Insert the required initial products without duplicating them."""
    products = [
        ("Product A", 100.00, 20),
        ("Product B", 50.00, 30),
        ("Product C", 200.00, 10),
    ]

    conn.executemany("""
        INSERT INTO products (name, unit_price, stock)
        VALUES (?, ?, ?)
        ON CONFLICT(name) DO NOTHING
    """, products)


if __name__ == "__main__":
    init_db()
    print(f"Database created/verified at: {DB_PATH}")

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT name, unit_price, stock, is_active
            FROM products
            ORDER BY id
        """).fetchall()

        print("\nInitial products:")
        for row in rows:
            print(
                f"{row['name']} | "
                f"Price: Rs. {row['unit_price']:.2f} | "
                f"Stock: {row['stock']} | "
                f"Active: {bool(row['is_active'])}"
            )
