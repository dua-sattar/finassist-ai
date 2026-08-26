"""Generate synthetic financial PDF documents for the FinAssist AI portfolio demo.

All content is entirely fictional (synthetic client IDs, names, account numbers,
transaction values) and generated with a fixed random seed for reproducibility.
Writes PDFs to data/synthetic/documents/ plus a manifest.csv describing each file.

Some documents are deliberately generated with a field missing, to give later
phases (structured extraction validation, document-review workflow) real
incomplete-document cases to demonstrate against. One deliberately corrupted,
non-PDF file is also written to exercise error handling in the parser.
"""

import csv
import random
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

SEED = 7
OUTPUT_DIR = Path(__file__).parent / "documents"

# (client_id, name) pairs pulled from clients.csv, used to keep documents linked
# to real synthetic client records.
CLIENTS = [
    ("C1001", "Allison Hill"),
    ("C1002", "Noah Rhodes"),
    ("C1003", "Angie Henderson"),
    ("C1004", "Daniel Wagner"),
    ("C1005", "Cristian Santos"),
    ("C1006", "Connie Lawrence"),
    ("C1007", "Abigail Shaffer"),
    ("C1009", "Gabrielle Davis"),
    ("C1010", "Ryan Munoz"),
    ("C1012", "Jamie Arnold"),
    ("C1017", "Holly Wood"),
    ("C1019", "Lisa Jackson"),
    ("C1025", "Matthew Foster"),
    ("C1034", "Nathan Maldonado"),
]

SERVICES = [
    "Retirement Planning",
    "Investment Advisory Consultation",
    "Tax Planning Consultation",
    "Estate Planning Guidance",
    "Business Financial Consulting",
]

MONTHS = ["March 2026", "April 2026", "May 2026", "June 2026", "July 2026", "August 2026"]


def draw_lines(c: canvas.Canvas, title: str, lines: list[str]) -> None:
    width, height = letter
    y = height - 1 * inch

    c.setFont("Helvetica-Bold", 14)
    c.drawString(1 * inch, y, title)
    y -= 0.15 * inch
    c.setFont("Helvetica", 8)
    c.drawString(1 * inch, y, "FinAssist AI -- Portfolio Demonstration -- Synthetic Data Only")
    y -= 0.4 * inch

    c.setFont("Helvetica", 11)
    for line in lines:
        c.drawString(1 * inch, y, line)
        y -= 0.3 * inch

    c.showPage()
    c.save()


def make_bank_statement(path: Path, client_id: str, name: str, omit_closing_balance: bool) -> None:
    account_number = f"AC-{random.randint(100000, 999999)}"
    period = random.choice(MONTHS)
    opening = round(random.uniform(2000, 40000), 2)
    deposits = round(random.uniform(1000, 15000), 2)
    withdrawals = round(random.uniform(500, 10000), 2)
    closing = round(opening + deposits - withdrawals, 2)

    lines = [
        f"Client ID: {client_id}",
        f"Client Name: {name}",
        f"Account Number: {account_number}",
        f"Statement Period: {period}",
        f"Opening Balance: ${opening:,.2f}",
        f"Total Deposits: ${deposits:,.2f}",
        f"Total Withdrawals: ${withdrawals:,.2f}",
    ]
    if not omit_closing_balance:
        lines.append(f"Closing Balance: ${closing:,.2f}")

    c = canvas.Canvas(str(path), pagesize=letter)
    draw_lines(c, "Bank Statement", lines)


def make_financial_summary(path: Path, client_id: str, name: str, omit_liabilities: bool) -> None:
    assets = round(random.uniform(50000, 500000), 2)
    liabilities = round(random.uniform(5000, 100000), 2)
    net_worth = round(assets - liabilities, 2)

    lines = [
        f"Client ID: {client_id}",
        f"Client Name: {name}",
        f"Total Assets: ${assets:,.2f}",
    ]
    if not omit_liabilities:
        lines.append(f"Total Liabilities: ${liabilities:,.2f}")
    lines.append(f"Estimated Net Worth: ${net_worth:,.2f}")

    c = canvas.Canvas(str(path), pagesize=letter)
    draw_lines(c, "Financial Summary", lines)


def make_transaction_report(path: Path, client_id: str, name: str) -> None:
    lines = [f"Client ID: {client_id}", f"Client Name: {name}", "Recent Transactions:"]
    for _ in range(5):
        day = random.randint(1, 28)
        amount = round(random.uniform(-2000, 2000), 2)
        sign = "-" if amount < 0 else "+"
        lines.append(f"  2026-07-{day:02d}   {sign}${abs(amount):,.2f}")

    c = canvas.Canvas(str(path), pagesize=letter)
    draw_lines(c, "Transaction Report", lines)


def make_application_form(path: Path, client_id: str, name: str, omit_signature: bool) -> None:
    lines = [
        f"Client ID: {client_id}",
        f"Full Name: {name}",
        f"Requested Service: {random.choice(SERVICES)}",
        f"Contact Email: {name.lower().replace(' ', '.')}@example.com",
    ]
    lines.append("Signature: __signed__" if not omit_signature else "Signature: (not provided)")

    c = canvas.Canvas(str(path), pagesize=letter)
    draw_lines(c, "Client Application Form", lines)


def make_account_summary(path: Path, client_id: str, name: str, omit_advisor: bool) -> None:
    lines = [
        f"Client ID: {client_id}",
        f"Client Name: {name}",
        f"Account Status: {random.choice(['Active', 'Pending'])}",
    ]
    if not omit_advisor:
        lines.append(f"Assigned Advisor: {random.choice(['Morgan Ellis', 'Priya Nandakumar', 'Sofia Reyes'])}")
    lines.append(f"Current Balance: ${round(random.uniform(1000, 60000), 2):,.2f}")

    c = canvas.Canvas(str(path), pagesize=letter)
    draw_lines(c, "Account Summary", lines)


def main() -> None:
    random.seed(SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    clients = list(CLIENTS)

    def next_client():
        return clients.pop(0)

    # 5 bank statements -- first one is the spec's own worked example (C1002, July 2026).
    special_path = OUTPUT_DIR / "C1002_bank_statement_july2026.pdf"
    c = canvas.Canvas(str(special_path), pagesize=letter)
    draw_lines(
        c,
        "Bank Statement",
        [
            "Client ID: C1002",
            "Client Name: Noah Rhodes",
            "Account Number: AC-500219",
            "Statement Period: July 2026",
            "Opening Balance: $25,000.00",
            "Total Deposits: $12,500.00",
            "Total Withdrawals: $8,200.00",
            "Closing Balance: $29,300.00",
        ],
    )
    manifest_rows.append(
        {
            "filename": special_path.name,
            "client_id": "C1002",
            "document_type": "bank_statement",
            "is_intentionally_incomplete": "No",
        }
    )

    bank_statement_incomplete_idx = 1  # 2nd remaining bank statement omits closing balance
    for i in range(4):
        cid, name = next_client()
        omit = i == bank_statement_incomplete_idx
        fname = f"{cid}_bank_statement.pdf"
        make_bank_statement(OUTPUT_DIR / fname, cid, name, omit_closing_balance=omit)
        manifest_rows.append(
            {
                "filename": fname,
                "client_id": cid,
                "document_type": "bank_statement",
                "is_intentionally_incomplete": "Yes" if omit else "No",
            }
        )

    # 3 financial summaries -- 1 omits liabilities.
    for i in range(3):
        cid, name = next_client()
        omit = i == 0
        fname = f"{cid}_financial_summary.pdf"
        make_financial_summary(OUTPUT_DIR / fname, cid, name, omit_liabilities=omit)
        manifest_rows.append(
            {
                "filename": fname,
                "client_id": cid,
                "document_type": "financial_summary",
                "is_intentionally_incomplete": "Yes" if omit else "No",
            }
        )

    # 3 transaction reports -- always complete.
    for _ in range(3):
        cid, name = next_client()
        fname = f"{cid}_transaction_report.pdf"
        make_transaction_report(OUTPUT_DIR / fname, cid, name)
        manifest_rows.append(
            {
                "filename": fname,
                "client_id": cid,
                "document_type": "transaction_report",
                "is_intentionally_incomplete": "No",
            }
        )

    # 2 application forms -- 1 omits signature.
    for i in range(2):
        cid, name = next_client()
        omit = i == 0
        fname = f"{cid}_application_form.pdf"
        make_application_form(OUTPUT_DIR / fname, cid, name, omit_signature=omit)
        manifest_rows.append(
            {
                "filename": fname,
                "client_id": cid,
                "document_type": "client_application_form",
                "is_intentionally_incomplete": "Yes" if omit else "No",
            }
        )

    # 2 account summaries -- 1 omits assigned advisor.
    for i in range(2):
        cid, name = next_client()
        omit = i == 0
        fname = f"{cid}_account_summary.pdf"
        make_account_summary(OUTPUT_DIR / fname, cid, name, omit_advisor=omit)
        manifest_rows.append(
            {
                "filename": fname,
                "client_id": cid,
                "document_type": "account_summary",
                "is_intentionally_incomplete": "Yes" if omit else "No",
            }
        )

    # Deliberately corrupted / non-PDF file to exercise parser error handling.
    corrupted_path = OUTPUT_DIR / "invalid_corrupted.pdf"
    corrupted_path.write_bytes(b"%PDF-1.4 THIS IS NOT A VALID PDF STREAM \x00\x01\x02 garbage")
    manifest_rows.append(
        {
            "filename": corrupted_path.name,
            "client_id": "",
            "document_type": "invalid",
            "is_intentionally_incomplete": "N/A",
        }
    )

    manifest_path = OUTPUT_DIR / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"Wrote {len(manifest_rows)} files to {OUTPUT_DIR}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
