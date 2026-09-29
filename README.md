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

- **Extracts structured data** from a photo or scan: vendor, invoice number,
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

python generate_sample.py                          # creates 2 test documents
python demo.py sample_documents/invoice_clean.png   # should extract cleanly
python demo.py sample_documents/invoice_suspicious.png  # should raise flags
```

The "suspicious" sample is deliberately broken (future-dated, total doesn't
match subtotal + tax) so you can see the flagging in action.

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

1. Swap `data/seen_invoices.json` for a real database so duplicate
   detection works properly across many users and restarts
2. Add a step to push extracted data into their actual system —
   Google Sheets, QuickBooks, Zoho, or a plain CSV export
3. Extend `EXTRACTION_TOOL`'s schema in `extractor.py` for
   industry-specific fields (e.g. policy number for insurance claims,
   waybill number for logistics)
4. For scanned PDFs (not just images), add a PDF-to-image conversion
   step before calling `extract()`

## Stack

- **Claude (Anthropic)** — vision + structured extraction via tool calling
- **Pillow** — only used to generate the synthetic sample documents

## Case study framing

*"Built an AI agent that reads invoices and receipts from photos/scans and
automatically extracts structured data, flagging math errors, duplicate
submissions, and future-dated documents before they reach a human —
cutting manual data entry and catching errors that used to slip through."*
