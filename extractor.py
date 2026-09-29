"""
Document extraction agent — core logic.

Takes a photo, scan, or PDF of an invoice/receipt/claim document and
returns clean, structured data plus a list of anomaly flags a human
should check. Persists everything to a real SQLite database (db.py).

--- Customizing EXTRACTION_TOOL for a specific industry ---

The schema below is generic (works for any invoice/receipt). For a real
client, add fields specific to their documents. Two examples:

  Insurance claims — add to the "properties" dict:
    "policy_number": {"type": "string"},
    "claimant_name": {"type": "string"},
    "incident_date": {"type": "string", "description": "ISO date"},

  Logistics / freight — add to the "properties" dict:
    "waybill_number": {"type": "string"},
    "origin": {"type": "string"},
    "destination": {"type": "string"},
    "weight_kg": {"type": "number"},

After adding fields, also add matching validation rules in `validate()`
below if the field should trigger a flag when missing or wrong (e.g.
flag any insurance claim with no policy_number).
"""

import base64
import json
import mimetypes
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
import anthropic

import db

load_dotenv()

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6"

EXTRACTION_TOOL = {
    "name": "record_invoice_data",
    "description": "Record the structured data extracted from an invoice, receipt, or claim document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "document_type": {"type": "string", "description": "e.g. invoice, receipt, claim form"},
            "vendor_or_issuer": {"type": "string"},
            "bill_to": {"type": "string"},
            "invoice_number": {"type": "string"},
            "date": {"type": "string", "description": "ISO format YYYY-MM-DD if determinable"},
            "payment_due": {"type": "string", "description": "ISO format YYYY-MM-DD if present"},
            "currency": {"type": "string", "description": "e.g. KES, USD"},
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "quantity": {"type": "string"},
                        "unit_price": {"type": "number"},
                        "amount": {"type": "number"},
                    },
                },
            },
            "subtotal": {"type": "number"},
            "tax": {"type": "number"},
            "total": {"type": "number"},
            "extraction_confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "How legible/clear the document was",
            },
            "notes": {"type": "string", "description": "Anything unusual or hard to read"},
        },
        "required": ["document_type", "total", "extraction_confidence"],
    },
}


SUPPORTED_IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
SUPPORTED_DOC_TYPES = {".pdf"}


def _build_content_block(path: Path) -> dict:
    """
    Builds the right content block for the file type. Images go in as
    "image" blocks; PDFs go in as "document" blocks — Claude reads PDFs
    natively (both the text and the visual layout of each page), no
    conversion needed. Max 32MB / 600 pages per Anthropic's limits.
    """
    suffix = path.suffix.lower()
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")

    if suffix in SUPPORTED_DOC_TYPES:
        return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}}

    if suffix in SUPPORTED_IMAGE_TYPES:
        media_type = mimetypes.guess_type(str(path))[0] or "image/png"
        return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}

    raise ValueError(
        f"Unsupported file type '{suffix}'. Supported: "
        f"{', '.join(sorted(SUPPORTED_IMAGE_TYPES | SUPPORTED_DOC_TYPES))}"
    )


def extract(file_path: str) -> dict:
    """Runs the document through Claude to pull structured fields (image or PDF)."""
    path = Path(file_path)
    content_block = _build_content_block(path)

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_invoice_data"},
        messages=[
            {
                "role": "user",
                "content": [
                    content_block,
                    {
                        "type": "text",
                        "text": (
                            "Extract all structured data from this invoice/receipt/claim "
                            "document using the record_invoice_data tool. If it's a "
                            "multi-page PDF, use the first page that looks like the main "
                            "invoice/receipt. Be precise with numbers. If something is "
                            "unclear or missing, say so in notes and lower your "
                            "extraction_confidence rather than guessing."
                        ),
                    },
                ],
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "record_invoice_data":
            return block.input

    raise RuntimeError("Model did not return structured extraction data.")


def validate(extracted: dict) -> list[str]:
    """Returns a list of human-readable flags for anything that looks off."""
    flags = []

    # Future-dated documents are almost always worth a second look
    doc_date = extracted.get("date")
    if doc_date:
        try:
            if date.fromisoformat(doc_date) > date.today():
                flags.append(f"Document is dated in the future ({doc_date}) — verify this is correct.")
        except ValueError:
            flags.append(f"Date field couldn't be parsed as a valid date: '{doc_date}'.")

    # Math check: subtotal + tax should ≈ total
    subtotal, tax, total = extracted.get("subtotal"), extracted.get("tax"), extracted.get("total")
    if subtotal is not None and tax is not None and total is not None:
        expected = round(subtotal + tax, 2)
        if abs(expected - total) > 1:  # allow tiny rounding differences
            flags.append(
                f"Total ({total}) doesn't match subtotal + tax ({expected}) — possible error or fraud."
            )

    # Duplicate invoice detection (checked against the database, not a JSON file)
    invoice_number = extracted.get("invoice_number")
    if invoice_number and db.has_seen_invoice(invoice_number):
        flags.append(f"Invoice number '{invoice_number}' has been seen before — possible duplicate submission.")

    # Low confidence extraction
    if extracted.get("extraction_confidence") == "low":
        flags.append("Extraction confidence is low — document may be blurry, cropped, or handwritten. Review manually.")

    # Missing critical fields
    if not extracted.get("total"):
        flags.append("No total amount could be extracted.")
    if not extracted.get("vendor_or_issuer"):
        flags.append("No vendor/issuer name could be extracted.")

    return flags


def process_document(file_path: str) -> dict:
    extracted = extract(file_path)
    flags = validate(extracted)  # checks against DB for duplicates BEFORE this doc is saved
    db.record_document(extracted, flags)  # now save it, so future duplicates get caught
    return {"extracted": extracted, "flags": flags}
