"""
Exports all processed documents from the database to a CSV file.

CSV is the universal adapter — QuickBooks, Zoho, Google Sheets, and Excel
all import CSV directly. This is usually the fastest way to get a client
live without building a custom integration for their specific system.

Usage:
    python export_csv.py                    # exports to data/export.csv
    python export_csv.py my_export.csv      # exports to a custom path

For a step further — auto-pushing into Google Sheets or QuickBooks
directly via their APIs — see the notes at the bottom of this file.
"""

import csv
import sys
from pathlib import Path

import db

FIELDNAMES = [
    "id",
    "processed_at",
    "invoice_number",
    "vendor_or_issuer",
    "document_date",
    "total",
    "currency",
    "extraction_confidence",
    "flags_json",
]


def export(output_path: str = "data/export.csv"):
    documents = db.get_all_documents(limit=10000)

    if not documents:
        print("No processed documents in the database yet. Run demo.py or web_app.py first.")
        return

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for doc in documents:
            writer.writerow({k: doc.get(k, "") for k in FIELDNAMES})

    print(f"Exported {len(documents)} document(s) to {path}")


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "data/export.csv"
    export(output)

# ---------------------------------------------------------------------------
# Going further: pushing directly into a client's actual system
# ---------------------------------------------------------------------------
#
# Google Sheets — use the `gspread` package with a service account:
#   pip install gspread google-auth
#   Then authenticate with a service account JSON key and call
#   worksheet.append_row([...]) for each document instead of writing CSV.
#   Docs: https://docs.gspread.org
#
# QuickBooks Online — use `python-quickbooks` or call their REST API
#   directly. Requires the client to authorize your app via OAuth2 in
#   their QuickBooks account (a one-time consent screen).
#   Docs: https://developer.intuit.com/app/developer/qbo/docs/get-started
#
# Zoho Books — similar OAuth2 flow, REST API accepts JSON directly.
#   Docs: https://www.zoho.com/books/api/v3/
#
# All three follow the same shape: authenticate once per client, then
# replace the CSV-writing loop above with an API call per document.
# Start with CSV for your first few clients — it works everywhere and
# needs zero setup on their end — then build a direct integration only
# once a client specifically asks for it (some will happily just import
# a CSV weekly).
