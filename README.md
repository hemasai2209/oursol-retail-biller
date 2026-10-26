# Mini Retail Biller & Sales Dashboard

## 1. Project Overview

The Mini Retail Biller & Sales Dashboard is a Python-based retail billing application built using Streamlit and SQLite. It helps a small retailer manage products, generate bills, track inventory, maintain transaction history, and analyze sales.

## 2. Technologies Used

- Python
- Streamlit
- SQLite
- HTML/CSS provided through Streamlit components and page styling, where applicable
- unittest for automated testing

## 3. Features

### Product Management
- Add products with a name, price, and available stock.
- Edit product details.
- Deactivate products without deleting historical transactions.
- Reactivate deactivated products.

### Billing
- Select products and quantities.
- Calculate subtotal, discount, and final amount.
- Generate unique bill numbers.
- Select payment method and payment status.
- Save bills and their line items in the database.
- Reduce stock for eligible bills.

### Transaction History
- Search for bills by bill number.
- Filter transactions.
- View bill details and line items.
- Cancel bills while retaining transaction history.
- Restore stock on eligible cancellations.

### Sales Dashboard
- View total sales, completed paid bill count, and average bill value.
- Identify best-selling products by quantity.
- Analyze sales by payment method.
- Search and review transactions.
- Exclude demo transactions by default.

## 4. Project Structure

```text
oursol_retail_biller/
├── app.py
├── database.py
├── billing.py
├── test_billing.py
├── README.md
└── retail.db
```

The `retail.db` database is created automatically when the application initializes. It may be generated locally rather than committed to the repository.

## 5. Setup and Run

### Prerequisites
- Python 3.10 or later recommended
- pip

### Install dependencies

Open a terminal in the project folder and run:

```bash
py -m pip install streamlit
```

### Initialize the database

```bash
py database.py
```

### Run the application

```bash
py -m streamlit run app.py
```

Streamlit will display a local URL in the terminal. Open that URL in your browser.

## 6. Run Automated Tests

Run the billing tests with:

```bash
py -m unittest test_billing.py -v
```

The tests cover bill calculations and selected validation and database behaviours. Check the test output to confirm that all tests pass.

## 7. Business Rules

- No tax is applied.
- Product prices must be positive.
- Quantities must be positive integers.
- Discounts must be between 0% and 100%.
- Bills are stored with their line items.
- Duplicate submissions with the same request ID are prevented by the billing logic.
- Failed payments do not reduce stock.
- Eligible bills reduce available stock.
- Cancellation preserves bill history and restores stock at most once.
- The dashboard excludes cancelled bills and unpaid or failed payments from its paid-sales metrics.
- Demo transactions are excluded from dashboard metrics by default.

### Example Calculation

For 2 units of Product A at ₹100 each and 1 unit of Product B at ₹50:

- Subtotal: ₹250
- Discount: 10% = ₹25
- Final amount: ₹225

## 8. Database Design

The SQLite database contains three main tables:

- `products`: product names, prices, stock, and active status.
- `bills`: bill numbers, totals, discount, payment information, and transaction status.
- `bill_items`: products and quantities recorded for each bill, including the product name and price at the time of billing.

The database uses constraints and foreign keys to help maintain data consistency. Application-level validation is also used.

## 9. Known Limitations

- This is a local demonstration application, not a production multi-user billing system.
- Authentication and role-based access control are not implemented.
- Payment processing is not integrated with a real payment gateway.
- Receipt printing uses the browser's print function; a dedicated PDF receipt may not be available.
- Automated tests cover selected business logic and database operations; they do not replace complete end-to-end testing.
- The database is local to the application environment unless separately configured.

## 10. AI Assistance Disclosure

AI assistance was used during development for guidance, debugging, and documentation. The implementation should be reviewed and tested by the developer, who must be able to explain the code, business rules, database operations, and test results.

## 11. Future Improvements

- Add user authentication and roles.
- Add export options for sales reports.
- Improve receipt formatting and PDF generation.
- Add broader integration and end-to-end tests.
- Improve handling of pending payments and payment reconciliation.
