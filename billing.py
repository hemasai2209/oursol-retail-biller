
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from uuid import uuid4

from database import get_connection


VALID_PAYMENT_METHODS = {
    "Cash",
    "UPI",
    "Card",
    "Bank Transfer",
}

VALID_PAYMENT_STATUSES = {
    "paid",
    "pending",
    "failed",
}


def money(value):
    """Round a monetary amount to two decimal places."""
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def calculate_bill(items, discount_percent=0):
    """
    Calculate a bill without saving it.

    items format:
    [
        {"name": "Product A", "unit_price": 100, "quantity": 2},
        {"name": "Product B", "unit_price": 50, "quantity": 1},
    ]
    """
    if not items:
        raise ValueError("Add at least one product to the bill.")

    discount = Decimal(str(discount_percent))

    if not discount.is_finite() or not Decimal("0") <= discount <= Decimal("100"):
        raise ValueError("Discount must be between 0 and 100 percent.")

    subtotal = Decimal("0.00")
    line_items = []

    for item in items:
        try:
            quantity = int(item["quantity"])
            price = Decimal(str(item["unit_price"]))
        except (KeyError, TypeError, ValueError):
            raise ValueError("Each item needs a valid price and quantity.")

        if isinstance(item["quantity"], bool) or quantity <= 0:
            raise ValueError("Product quantities must be positive whole numbers.")

        if not price.is_finite() or price <= 0:
            raise ValueError("Product prices must be greater than zero.")

        line_total = money(price * quantity)
        subtotal += line_total

        line_items.append({
            "name": item.get("name", "Product"),
            "unit_price": money(price),
            "quantity": quantity,
            "line_total": line_total,
        })

    subtotal = money(subtotal)
    discount_amount = money(subtotal * discount / Decimal("100"))
    total = money(subtotal - discount_amount)

    return {
        "items": line_items,
        "subtotal": subtotal,
        "discount_percent": discount,
        "discount_amount": discount_amount,
        "total": total,
    }


def create_bill(
    items,
    discount_percent,
    payment_method,
    payment_status,
    request_id,
    is_demo=False,
):
    """
    Validate and save a bill in one database transaction.

    Each item must contain product_id and quantity.
    request_id must be reused when retrying the same submission.
    """
    if not request_id:
        raise ValueError("A request ID is required to prevent duplicate bills.")

    if payment_method not in VALID_PAYMENT_METHODS:
        raise ValueError("Select a valid payment method.")

    if payment_status not in VALID_PAYMENT_STATUSES:
        raise ValueError("Select a valid payment status.")

    if not items:
        raise ValueError("Add at least one product.")

    conn = get_connection()

    try:
        # Prevent concurrent bills from overselling the same stock.
        conn.execute("BEGIN IMMEDIATE")

        existing = conn.execute(
            "SELECT bill_number FROM bills WHERE request_id = ?",
            (request_id,),
        ).fetchone()

        if existing:
            conn.rollback()
            return existing["bill_number"]

        saved_items = []

        for item in items:
            try:
                product_id = int(item["product_id"])
                quantity = int(item["quantity"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("Each item needs a product ID and quantity.")

            if isinstance(item["quantity"], bool) or quantity <= 0:
                raise ValueError("Quantities must be positive whole numbers.")

            product = conn.execute("""
                SELECT id, name, unit_price, stock, is_active
                FROM products
                WHERE id = ?
            """, (product_id,)).fetchone()

            if product is None:
                raise ValueError("A selected product does not exist.")

            if product["is_active"] != 1:
                raise ValueError(
                    f"{product['name']} is inactive and cannot be sold."
                )

            if quantity > product["stock"] and payment_status != "failed":
                raise ValueError(
                    f"Insufficient stock for {product['name']}. "
                    f"Available: {product['stock']}."
                )

            saved_items.append({
                "product_id": product["id"],
                "name": product["name"],
                "unit_price": product["unit_price"],
                "quantity": quantity,
            })

        calculation = calculate_bill(saved_items, discount_percent)

        bill_number = (
            "BILL-"
            + datetime.now().strftime("%Y%m%d")
            + "-"
            + uuid4().hex[:8].upper()
        )

        cursor = conn.execute("""
            INSERT INTO bills (
                bill_number, request_id, subtotal,
                discount_percent, discount_amount, total_amount,
                payment_method, payment_status, status, is_demo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bill_number,
            request_id,
            float(calculation["subtotal"]),
            float(calculation["discount_percent"]),
            float(calculation["discount_amount"]),
            float(calculation["total"]),
            payment_method,
            payment_status,
            "cancelled" if payment_status == "failed" else "completed",
            int(is_demo),
        ))

        bill_id = cursor.lastrowid

        for item in saved_items:
            price = money(item["unit_price"])
            line_total = money(price * item["quantity"])

            conn.execute("""
                INSERT INTO bill_items (
                    bill_id, product_id, product_name,
                    quantity, unit_price, line_total
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                bill_id,
                item["product_id"],
                item["name"],
                item["quantity"],
                float(price),
                float(line_total),
            ))

            # Failed payments do not reduce stock.
            if payment_status != "failed":
                update = conn.execute("""
                    UPDATE products
                    SET stock = stock - ?
                    WHERE id = ? AND is_active = 1 AND stock >= ?
                """, (
                    item["quantity"],
                    item["product_id"],
                    item["quantity"],
                ))

                if update.rowcount != 1:
                    raise ValueError(
                        f"Stock changed while billing {item['name']}. "
                        "Please refresh and try again."
                    )

        conn.commit()
        return bill_number

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def cancel_bill(bill_number):
    """
    Cancel a bill without deleting its history.
    Restore stock at most once for non-failed payments.
    """
    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        bill = conn.execute("""
            SELECT id, status, payment_status, stock_restored
            FROM bills
            WHERE bill_number = ?
        """, (bill_number,)).fetchone()

        if bill is None:
            raise ValueError("Bill number was not found.")

        if bill["status"] == "cancelled":
            raise ValueError("This bill has already been cancelled.")

        if bill["payment_status"] == "refunded":
            raise ValueError("This bill has already been refunded.")

        if bill["payment_status"] != "failed" and not bill["stock_restored"]:
            bill_items = conn.execute("""
                SELECT product_id, quantity
                FROM bill_items
                WHERE bill_id = ?
            """, (bill["id"],)).fetchall()

            for item in bill_items:
                # A product may have been deleted after a sale.
                if item["product_id"] is not None:
                    conn.execute("""
                        UPDATE products
                        SET stock = stock + ?
                        WHERE id = ?
                    """, (item["quantity"], item["product_id"]))

        conn.execute("""
            UPDATE bills
            SET status = 'cancelled', stock_restored = 1
            WHERE id = ?
        """, (bill["id"],))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    test_items = [
        {"name": "Product A", "unit_price": 100, "quantity": 2},
        {"name": "Product B", "unit_price": 50, "quantity": 1},
    ]

    result = calculate_bill(test_items, 10)

    print("Billing calculation test")
    print("Subtotal:", result["subtotal"])
    print("Discount:", result["discount_amount"])
    print("Final amount:", result["total"])
