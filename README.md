# Document Processing Agent

An AI agent that reads invoices, receipts, and claim documents (photos or
scans) and turns them into clean, structured data — while automatically
flagging anything that looks wrong: math errors, future-dated documents,
duplicate invoice numbers, or blurry/incomplete scans.

Built for insurance, logistics, and accounting workflows where someone is
currently manually retyping numbers off paper or photos into a spreadsheet
or system.

## The problem this solves

Manual invoice/claim processing is slow and error-prone:
- Staff retype numbers from photos/scans into Excel or an accounting system
- Math errors, duplicate submissions, and altered documents slip through
  because no one has time to double-check every line
- Processing backs up when volume spikes, delaying payments and claims

## What the agent does

- **Reads images and PDFs** — photos, scans, or native PDF invoices/receipts
  (Claude processes PDFs natively, both text and visual layout, up to
  32MB/600 pages — no separate conversion step needed)
- **Extracts structured data**: vendor, invoice number,
  date, line items, subtotal, tax, total, currency
- **Flags anomalies automatically**:
  - Totals that don't match subtotal + tax
  - Future-dated documents
  - Duplicate invoice numbers (already seen before)
  - Low-confidence/blurry extractions that need a human to check
  - Missing critical fields (no total, no vendor name)
- **Never silently guesses** — if the document is unclear, it says so
  instead of inventing a number

## Try it right now

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your real ANTHROPIC_API_KEY

python generate_sample.py   # creates 2 test documents
```

**Option A — browser demo (use this one for client demos / videos):**

```bash
uvicorn web_app:app --reload --port 8000
```

Open http://localhost:8000, drag in `sample_documents/invoice_clean.png`,
then try `sample_documents/invoice_suspicious.png` to see the flagging
happen live in the browser.

**Option B — command line:**

```bash
python demo.py sample_documents/invoice_clean.png
python demo.py sample_documents/invoice_suspicious.png
```

The "suspicious" sample is deliberately broken (future-dated, total doesn't
match subtotal + tax) so you can see the flagging in action either way.

## Architecture

```
Photo/scan of invoice
        │
        ▼
  extractor.py ── extract() ──▶ Claude (vision + structured tool output)
        │
        ▼
  extractor.py ── validate() ──▶ checks: math, dates, duplicates, confidence
        │
        ▼
  Clean structured JSON + list of flags for human review
```

## Adapting this for a real client

1. **Database** — already done: `db.py` uses a real SQLite database
   (`data/documents.db`) instead of a JSON file, so duplicate-invoice
   detection survives restarts. Every processed document is saved with
   its full extracted data. For a client with multiple people hitting
   this from different machines, swap SQLite for Postgres (same function
   signatures in `db.py`, just a different connection).

2. **Exporting to their system** — already done for CSV: run
   `python export_csv.py` any time to export everything processed so far
   to `data/export.csv`, which opens directly in Excel or imports into
   QuickBooks/Zoho/Google Sheets. `demo.py` runs this automatically after
   each batch. For a client who wants it pushed automatically (no manual
   import step), see the notes at the bottom of `export_csv.py` for
   wiring up the Google Sheets, QuickBooks, or Zoho APIs directly.

3. **Industry-specific fields** — see the docstring at the top of
   `extractor.py` for concrete examples (insurance claim fields,
   logistics/freight fields) and how to add matching validation rules.

4. **PDFs** — already handled natively; see "What the agent does" above.

## Stack

- **Claude (Anthropic)** — vision + structured extraction via tool calling
- **Pillow** — only used to generate the synthetic sample documents

## Case study framing

*"Built an AI agent that reads invoices and receipts from photos/scans and
automatically extracts structured data, flagging math errors, duplicate
submissions, and future-dated documents before they reach a human —
cutting manual data entry and catching errors that used to slip through."*
