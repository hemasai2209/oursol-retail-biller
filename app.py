
import streamlit as st
from uuid import uuid4
from datetime import date


from database import init_db, get_connection
from billing import create_bill, cancel_bill

st.set_page_config(
    page_title="OURSOL Retail Biller",
    page_icon="🛒",
    layout="wide",
)

init_db()

st.title("OURSOL Mini Retail Biller")
st.caption("Product management and retail billing")

page = st.sidebar.radio(
    "Navigation",
    ["Product Management", "Create Bill", "Transaction History", "Sales Dashboard"],
)

def fetch_all(query, params=()):
    conn = get_connection()
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def get_products(active_only=False):
    query = """
        SELECT id, name, unit_price, stock, is_active
        FROM products
    """
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY id"
    return fetch_all(query)


def load_bill(bill_number):
    bills = fetch_all(
        "SELECT * FROM bills WHERE bill_number = ?",
        (bill_number,),
    )
    if not bills:
        return None, []

    bill = bills[0]
    items = fetch_all(
        """
        SELECT product_name, quantity, unit_price, line_total
        FROM bill_items
        WHERE bill_id = ?
        ORDER BY id
        """,
        (bill["id"],),
    )
    return bill, items



def show_receipt(bill_number):
    bill, items = load_bill(bill_number)

    if bill is None:
        st.error("The saved bill could not be found.")
        return

    st.markdown(
    """
    

<style>
@page {
    size: A4 portrait;
    margin: 10mm;
}

@media print {
    html,
    body {
        height: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }

    body * {
        visibility: hidden !important;
    }

    .receipt-print,
    .receipt-print * {
        visibility: visible !important;
    }

    .receipt-print {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        right: auto !important;
        width: 100% !important;
        max-width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
        box-sizing: border-box !important;
        background: #fff !important;
        color: #000 !important;
        font-size: 10pt !important;
        text-align: left !important;
        transform: none !important;
        overflow: visible !important;
    }

    .receipt-print h2,
    .receipt-print h3,
    .receipt-print p {
        text-align: left !important;
        color: #000 !important;
        margin: 4px 0 !important;
    }

    .receipt-print table {
        width: 100% !important;
        table-layout: fixed !important;
        border-collapse: collapse !important;
        margin: 8px 0 !important;
    }

    .receipt-print th,
    .receipt-print td {
        border: 1px solid #999 !important;
        padding: 6px !important;
        color: #000 !important;
        text-align: left !important;
        overflow-wrap: anywhere !important;
    }

    .receipt-print tr {
        break-inside: avoid !important;
        page-break-inside: avoid !important;
    }

    .receipt-print * {
        box-shadow: none !important;
    }
}
</style>

    """,
    unsafe_allow_html=True,
)
    st.markdown(
        f"""
        <div class="receipt-print">
            <h2 style="text-align:center;">OURSOL Retail Biller</h2>
            <p style="text-align:center;">Sales Receipt</p>
            <hr>
            <p><strong>Bill number:</strong> {bill['bill_number']}</p>
            <p><strong>Date and time:</strong> {bill['created_at']}</p>
            <p><strong>Payment method:</strong> {bill['payment_method']}</p>
            <p><strong>Payment status:</strong> {bill['payment_status'].title()}</p>
            <p><strong>Bill status:</strong> {bill['status'].title()}</p>
            <table>
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Qty</th>
                        <th>Unit price</th>
                        <th class="amount">Line total</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(
                        f"<tr><td>{item['product_name']}</td>"
                        f"<td>{item['quantity']}</td>"
                        f"<td>₹{item['unit_price']:.2f}</td>"
                        f"<td class='amount'>₹{item['line_total']:.2f}</td></tr>"
                        for item in items
                    )}
                </tbody>
            </table>
            <hr>
            <p class="amount"><strong>Subtotal: ₹{bill['subtotal']:.2f}</strong></p>
            <p class="amount">Discount ({bill['discount_percent']:.2f}%):
                −₹{bill['discount_amount']:.2f}</p>
            <h2 class="amount">Final amount: ₹{bill['total_amount']:.2f}</h2>
            <p style="text-align:center;">Thank you for shopping!</p>
            <p style="text-align:center;">Tax is disabled.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "To print the receipt, press Ctrl+P in your browser. "
        "Check Print Preview before printing."
    )



# --------------------------------------------------
# PRODUCT MANAGEMENT
# --------------------------------------------------
if page == "Product Management":
    st.header("Product Management")

    products = get_products()
    active_products = [p for p in products if p["is_active"] == 1]

    col1, col2 = st.columns(2)
    col1.metric("Total products", len(products))
    col2.metric("Active products", len(active_products))

    st.subheader("Inventory")

    st.dataframe(
        [
            {
                "ID": p["id"],
                "Product": p["name"],
                "Unit price (₹)": f"{p['unit_price']:.2f}",
                "Stock": p["stock"],
                "Status": "Active" if p["is_active"] else "Inactive",
            }
            for p in products
        ],
        use_container_width=True,
        hide_index=True,
    )

    add_tab, edit_tab, deactivate_tab, reactivate_tab = st.tabs(
        ["Add Product", "Edit Product", "Deactivate", "Reactivate"]
    )

    with add_tab:
        with st.form("add_product_form"):
            name = st.text_input("Product name").strip()
            price = st.number_input(
                "Unit price (₹)", min_value=0.0,
                value=100.0, step=1.0, format="%.2f"
            )
            stock = st.number_input(
                "Available stock", min_value=0, value=0, step=1
            )
            add_clicked = st.form_submit_button("Add product")

        if add_clicked:
            if not name:
                st.error("Product name cannot be empty.")
            elif price <= 0:
                st.error("Price must be greater than zero.")
            else:
                conn = get_connection()
                try:
                    conn.execute(
                        """
                        INSERT INTO products (name, unit_price, stock)
                        VALUES (?, ?, ?)
                        """,
                        (name, float(price), int(stock)),
                    )
                    conn.commit()
                    st.success("Product added successfully.")
                    st.rerun()
                except Exception as exc:
                    conn.rollback()
                    st.error(f"Could not add product: {exc}")
                finally:
                    conn.close()

    with edit_tab:
        if products:
            labels = {
                f"{p['id']} — {p['name']}": p["id"]
                for p in products
            }
            label = st.selectbox("Choose product", list(labels.keys()))
            selected = next(p for p in products if p["id"] == labels[label])

            with st.form("edit_product_form"):
                edit_name = st.text_input(
                    "Product name", value=selected["name"]
                ).strip()
                edit_price = st.number_input(
                    "Unit price (₹)",
                    min_value=0.0,
                    value=float(selected["unit_price"]),
                    step=1.0,
                    format="%.2f",
                )
                edit_stock = st.number_input(
                    "Available stock",
                    min_value=0,
                    value=int(selected["stock"]),
                    step=1,
                )
                edit_clicked = st.form_submit_button("Save changes")

            if edit_clicked:
                if not edit_name:
                    st.error("Product name cannot be empty.")
                elif edit_price <= 0:
                    st.error("Price must be greater than zero.")
                else:
                    conn = get_connection()
                    try:
                        conn.execute(
                            """
                            UPDATE products
                            SET name = ?, unit_price = ?, stock = ?
                            WHERE id = ?
                            """,
                            (
                                edit_name,
                                float(edit_price),
                                int(edit_stock),
                                selected["id"],
                            ),
                        )
                        conn.commit()
                        st.success("Product updated.")
                        st.rerun()
                    except Exception as exc:
                        conn.rollback()
                        st.error(f"Could not update product: {exc}")
                    finally:
                        conn.close()
        else:
            st.info("No products available.")

    with deactivate_tab:
        active = [p for p in products if p["is_active"] == 1]

        if active:
            options = {f"{p['id']} — {p['name']}": p["id"] for p in active}
            label = st.selectbox(
                "Product to deactivate",
                list(options.keys()),
                key="deactivate_choice",
            )
            confirmed = st.checkbox(
                "Confirm deactivation", key="deactivate_confirm"
            )

            if st.button("Deactivate product"):
                if not confirmed:
                    st.warning("Please confirm deactivation.")
                else:
                    conn = get_connection()
                    try:
                        conn.execute(
                            "UPDATE products SET is_active = 0 WHERE id = ?",
                            (options[label],),
                        )
                        conn.commit()
                        st.success("Product deactivated; record preserved.")
                        st.rerun()
                    finally:
                        conn.close()
        else:
            st.info("No active products.")

    with reactivate_tab:
        inactive = [p for p in products if p["is_active"] == 0]

        if inactive:
            options = {
                f"{p['id']} — {p['name']}": p["id"]
                for p in inactive
            }
            label = st.selectbox(
                "Product to reactivate",
                list(options.keys()),
                key="reactivate_choice",
            )

            if st.button("Reactivate product"):
                conn = get_connection()
                try:
                    conn.execute(
                        "UPDATE products SET is_active = 1 WHERE id = ?",
                        (options[label],),
                    )
                    conn.commit()
                    st.success("Product reactivated.")
                    st.rerun()
                finally:
                    conn.close()
        else:
            st.info("No inactive products.")


# --------------------------------------------------
# BILLING
# --------------------------------------------------
elif page == "Create Bill":
    st.header("Create a bill")

    products = get_products(active_only=True)
    available = [p for p in products if p["stock"] > 0]

    if not products:
        st.warning("Add or reactivate a product before creating a bill.")
    else:
        st.caption("Enter a quantity of zero to leave a product out of the bill.")

        # Keep one request ID for retries of the same bill submission.
        if "billing_request_id" not in st.session_state:
            st.session_state["billing_request_id"] = uuid4().hex

        request_id = st.session_state["billing_request_id"]

        with st.form(f"billing_form_{request_id}"):
            quantities = {}

            for product in products:
                st.write(
                    f"**{product['name']}** — "
                    f"₹{product['unit_price']:.2f} each | "
                    f"Available stock: {product['stock']}"
                )
                quantities[product["id"]] = st.number_input(
                    f"Quantity — {product['name']}",
                    min_value=0,
                    max_value=max(0, int(product["stock"])),
                    value=0,
                    step=1,
                    key=f"quantity_{request_id}_{product['id']}",
                    disabled=(product["stock"] == 0),
                )

            discount = st.number_input(
                "Discount (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=1.0,
                key=f"discount_{request_id}",
            )

            payment_method = st.selectbox(
                "Payment method",
                ["Cash", "UPI", "Card", "Bank Transfer"],
                key=f"method_{request_id}",
            )

            payment_status = st.selectbox(
                "Payment status",
                ["paid", "pending", "failed"],
                format_func=lambda value: value.title(),
                key=f"payment_status_{request_id}",
            )
            is_demo = st.checkbox(
                "Demo transaction (test data only)",
                value=False,
                help="Demo bills are excluded from dashboard totals by default.",
            )
            submitted = st.form_submit_button("Generate bill")

        if submitted:
            selected_items = [
                {
                    "product_id": product["id"],
                    "quantity": int(quantities[product["id"]]),
                }
                for product in products
                if quantities[product["id"]] > 0
            ]

            if not selected_items:
                st.error("Select at least one product with a quantity above zero.")
            else:
                try:
                    bill_number = create_bill(
                        items=selected_items,
                        discount_percent=discount,
                        payment_method=payment_method,
                        payment_status=payment_status,
                        request_id=request_id,
                        is_demo=is_demo,
                    )

                    st.session_state["last_bill_number"] = bill_number
                    st.session_state["billing_request_id"] = uuid4().hex

                    st.success(f"Bill saved successfully: {bill_number}")
                    st.rerun()

                except (ValueError, KeyError) as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Could not save the bill: {exc}")

    # Show the latest saved receipt on this page.
    last_bill = st.session_state.get("last_bill_number")
    if last_bill:
        st.divider()
        show_receipt(last_bill)


# --------------------------------------------------
# TRANSACTION HISTORY
# --------------------------------------------------
elif page == "Transaction History":
    st.header("Transaction History")
    st.caption(
        "Search saved bills, review line items, and cancel transactions "
        "without deleting historical records."
    )

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "From date",
            value=date.today().replace(month=1, day=1),
            key="history_start_date",
        )

    with col2:
        end_date = st.date_input(
            "To date",
            value=date.today(),
            key="history_end_date",
        )

    search_bill = st.text_input(
        "Search by bill number",
        placeholder="Example: BILL-20261026-AB12CD34",
    ).strip()

    payment_filter = st.selectbox(
        "Payment status",
        ["All", "paid", "pending", "failed", "refunded"],
        format_func=lambda value: (
            "All payment statuses" if value == "All" else value.title()
        ),
    )

    if start_date > end_date:
        st.error("The start date cannot be after the end date.")
    else:
        query = """
            SELECT
                id, bill_number, created_at, subtotal,
                discount_amount, total_amount, payment_method,
                payment_status, status, is_demo
            FROM bills
            WHERE date(created_at) BETWEEN ? AND ?
        """
        params = [start_date.isoformat(), end_date.isoformat()]

        if search_bill:
            query += " AND bill_number LIKE ?"
            params.append(f"%{search_bill}%")

        if payment_filter != "All":
            query += " AND payment_status = ?"
            params.append(payment_filter)

        query += " ORDER BY created_at DESC, id DESC"

        bills = fetch_all(query, tuple(params))

        st.subheader(f"Matching transactions: {len(bills)}")

        if bills:
            st.dataframe(
                [
                    {
                        "Bill number": b["bill_number"],
                        "Date": b["created_at"],
                        "Subtotal (₹)": f"{b['subtotal']:.2f}",
                        "Discount (₹)": f"{b['discount_amount']:.2f}",
                        "Total (₹)": f"{b['total_amount']:.2f}",
                        "Payment method": b["payment_method"],
                        "Payment status": b["payment_status"].title(),
                        "Bill status": b["status"].title(),
                        "Demo": "Yes" if b["is_demo"] else "No",
                    }
                    for b in bills
                ],
                use_container_width=True,
                hide_index=True,
            )

            st.divider()
            st.subheader("View bill details")

            bill_options = {
                f"{b['bill_number']} — {b['status'].title()}": b["bill_number"]
                for b in bills
            }

            selected_label = st.selectbox(
                "Choose a bill",
                list(bill_options.keys()),
                key="history_selected_bill",
            )

            selected_number = bill_options[selected_label]
            selected_bill, selected_items = load_bill(selected_number)

            if selected_bill:
                show_receipt(selected_number)

                if selected_bill["status"] == "completed":
                    st.warning(
                        "Cancelling preserves the bill history and restores "
                        "stock once, for bills whose payment did not fail."
                    )

                    confirm_cancel = st.checkbox(
                        f"I confirm cancellation of {selected_number}.",
                        key=f"confirm_cancel_{selected_number}",
                    )

                    if st.button(
                        "Cancel selected bill",
                        key=f"cancel_button_{selected_number}",
                    ):
                        if not confirm_cancel:
                            st.warning(
                                "Please confirm cancellation before continuing."
                            )
                        else:
                            try:
                                cancel_bill(selected_number)
                                st.success(
                                    f"{selected_number} was cancelled. "
                                    "The historical record remains saved."
                                )
                                st.rerun()
                            except ValueError as exc:
                                st.error(str(exc))
                            except Exception as exc:
                                st.error(f"Could not cancel bill: {exc}")
                else:
                    st.info(
                        "This bill is already cancelled and cannot be "
                        "cancelled again."
                    )
        else:
            st.info("No transactions match the selected filters.")

# --------------------------------------------------
# SALES DASHBOARD
# --------------------------------------------------
elif page == "Sales Dashboard":
    st.header("Sales Dashboard")
    st.caption("Business metrics calculated from saved database records.")

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Start date",
            value=date.today().replace(month=1, day=1),
            key="dashboard_start_date",
        )

    with col2:
        end_date = st.date_input(
            "End date",
            value=date.today(),
            key="dashboard_end_date",
        )

    include_demo = st.checkbox(
        "Include demo transactions",
        value=False,
        help="Demo transactions are excluded by default.",
    )

    if start_date > end_date:
        st.error("The start date cannot be after the end date.")
    else:
        start = start_date.isoformat()
        end = end_date.isoformat()

        demo_condition = "" if include_demo else " AND is_demo = 0"
        

        # Completed sales means completed bills with paid status.
        sales_query = """
            SELECT
                COUNT(*) AS completed_bills,
                COALESCE(SUM(total_amount), 0) AS total_sales,
                COALESCE(AVG(total_amount), 0) AS average_bill
            FROM bills
            WHERE date(created_at) BETWEEN ? AND ?
              AND status = 'completed'
              AND payment_status = 'paid'
        """ + demo_condition

        summary = fetch_all(
            sales_query,
            (start, end),
        )[0]

        st.subheader("Sales overview")

        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Completed sales",
            f"₹{summary['total_sales']:,.2f}",
        )
        c2.metric(
            "Completed bills",
            int(summary["completed_bills"]),
        )
        c3.metric(
            "Average bill value",
            f"₹{summary['average_bill']:,.2f}",
        )

        st.caption(
            "Sales metrics include only paid bills that are not cancelled. "
            "Average bill value = completed sales ÷ completed bill count."
        )

        st.divider()

        # Best-selling product by quantity sold.
        st.subheader("Best-selling product")

        best_query = """
            SELECT
                bi.product_name,
                SUM(bi.quantity) AS units_sold
            FROM bill_items bi
            JOIN bills b ON b.id = bi.bill_id
            WHERE date(b.created_at) BETWEEN ? AND ?
              AND b.status = 'completed'
              AND b.payment_status = 'paid'
        """

        best_query += (
            " AND b.is_demo = 0" if not include_demo else ""
        )

        best_query += """
            GROUP BY bi.product_name
            ORDER BY units_sold DESC, bi.product_name ASC
            LIMIT 1
        """

        best = fetch_all(best_query, (start, end))

        if best:
            st.metric(
                "Top product",
                best[0]["product_name"],
                f"{best[0]['units_sold']} units sold",
            )
        else:
            st.info("No qualifying product sales in this date range.")

        # Sales grouped by payment method.
        st.subheader("Sales by payment method")

        method_query = """
            SELECT
                payment_method,
                COUNT(*) AS bill_count,
                SUM(total_amount) AS sales_amount
            FROM bills
            WHERE date(created_at) BETWEEN ? AND ?
              AND status = 'completed'
              AND payment_status = 'paid'
        """

        method_query += (
            " AND is_demo = 0" if not include_demo else ""
        )

        method_query += """
            GROUP BY payment_method
            ORDER BY sales_amount DESC
        """

        methods = fetch_all(method_query, (start, end))

        if methods:
            st.dataframe(
                [
                    {
                        "Payment method": row["payment_method"],
                        "Completed bills": row["bill_count"],
                        "Sales (₹)": f"{row['sales_amount']:.2f}",
                    }
                    for row in methods
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No completed payments found for this period.")

        # Searchable and filterable transaction table.
        st.divider()
        st.subheader("Transactions")

        search_text = st.text_input(
            "Search bill number",
            key="dashboard_bill_search",
        ).strip()

        status_filter = st.selectbox(
            "Bill status",
            ["All", "completed", "cancelled"],
            format_func=lambda value: (
                "All bill statuses" if value == "All" else value.title()
            ),
            key="dashboard_bill_status_filter",
        )

        payment_filter = st.selectbox(
            "Payment status",
            ["All", "paid", "pending", "failed", "refunded"],
            format_func=lambda value: (
                "All payment statuses" if value == "All" else value.title()
            ),
            key="dashboard_payment_filter",
        )

        transaction_query = """
            SELECT
                bill_number, created_at, total_amount,
                payment_method, payment_status, status, is_demo
            FROM bills
            WHERE date(created_at) BETWEEN ? AND ?
        """

        transaction_params = [start, end]

        if not include_demo:
            transaction_query += " AND is_demo = 0"

        if search_text:
            transaction_query += " AND bill_number LIKE ?"
            transaction_params.append(f"%{search_text}%")

        if status_filter != "All":
            transaction_query += " AND status = ?"
            transaction_params.append(status_filter)

        if payment_filter != "All":
            transaction_query += " AND payment_status = ?"
            transaction_params.append(payment_filter)

        transaction_query += " ORDER BY created_at DESC"

        transactions = fetch_all(
            transaction_query,
            tuple(transaction_params),
        )

        if transactions:
            st.dataframe(
                [
                    {
                        "Bill number": row["bill_number"],
                        "Date": row["created_at"],
                        "Total (₹)": f"{row['total_amount']:.2f}",
                        "Payment method": row["payment_method"],
                        "Payment status": row["payment_status"].title(),
                        "Bill status": row["status"].title(),
                        "Demo": "Yes" if row["is_demo"] else "No",
                    }
                    for row in transactions
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No transactions match the selected filters.")
