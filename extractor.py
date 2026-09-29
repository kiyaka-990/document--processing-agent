"""
Document extraction agent — core logic.

Takes a photo or scan of an invoice/receipt/claim document and returns
clean, structured data plus a list of anomaly flags a human should check.

Swap the `record_seen_invoice` / `has_seen_invoice` functions for a real
database lookup in production (currently uses a local JSON file) so
duplicate-invoice detection works across restarts and across users.
"""

import base64
import json
import mimetypes
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
import anthropic

load_dotenv()

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
SEEN_INVOICES_FILE = DATA_DIR / "seen_invoices.json"

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


def _encode_image(path: Path) -> dict:
    media_type = mimetypes.guess_type(str(path))[0] or "image/png"
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return {"type": "base64", "media_type": media_type, "data": data}


def extract(file_path: str) -> dict:
    """Runs the document through Claude's vision to pull structured fields."""
    path = Path(file_path)
    image_source = _encode_image(path)

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_invoice_data"},
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": image_source},
                    {
                        "type": "text",
                        "text": (
                            "Extract all structured data from this invoice/receipt/claim "
                            "document using the record_invoice_data tool. Be precise with "
                            "numbers. If something is unclear or missing, say so in notes "
                            "and lower your extraction_confidence rather than guessing."
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


def _load_seen_invoices() -> set:
    if SEEN_INVOICES_FILE.exists():
        return set(json.loads(SEEN_INVOICES_FILE.read_text()))
    return set()


def _mark_seen(invoice_number: str):
    seen = _load_seen_invoices()
    seen.add(invoice_number)
    SEEN_INVOICES_FILE.write_text(json.dumps(sorted(seen), indent=2))


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

    # Duplicate invoice detection
    invoice_number = extracted.get("invoice_number")
    if invoice_number:
        if invoice_number in _load_seen_invoices():
            flags.append(f"Invoice number '{invoice_number}' has been seen before — possible duplicate submission.")
        else:
            _mark_seen(invoice_number)

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
    flags = validate(extracted)
    return {"extracted": extracted, "flags": flags}
