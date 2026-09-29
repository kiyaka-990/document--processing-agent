"""
Generates a couple of synthetic sample invoice/receipt images so you can
test the extraction agent immediately, without needing real client
documents yet. Run this once:

    python generate_sample.py

Replace these with real (sanitized) client documents once you have them.
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT_DIR = Path(__file__).parent / "sample_documents"
OUT_DIR.mkdir(exist_ok=True)


def _font(size):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def make_invoice(filename, lines, title="INVOICE"):
    img = Image.new("RGB", (800, 1000), color="white")
    draw = ImageDraw.Draw(img)
    y = 40
    draw.text((40, y), title, fill="black", font=_font(32))
    y += 60
    for line in lines:
        draw.text((40, y), line, fill="black", font=_font(20))
        y += 34
    img.save(OUT_DIR / filename)
    print(f"Created {OUT_DIR / filename}")


make_invoice(
    "invoice_clean.png",
    [
        "Asterleigh Freight & Logistics Ltd",
        "P.O. Box 4521, Nairobi, Kenya",
        "",
        "Invoice #: INV-2026-0847",
        "Date: 2026-09-15",
        "Bill To: Mazuri Enterprises Ltd",
        "",
        "Description              Qty    Unit Price    Amount",
        "Freight - Nairobi/Mombasa  1     KES 45,000    KES 45,000",
        "Loading & handling         1     KES 5,000     KES 5,000",
        "Insurance surcharge        1     KES 2,500     KES 2,500",
        "",
        "Subtotal:                              KES 52,500",
        "VAT (16%):                             KES 8,400",
        "Total:                                 KES 60,900",
        "",
        "Payment due: 2026-09-30",
        "M-Pesa Paybill: 400200, Account: INV20260847",
    ],
)

make_invoice(
    "invoice_suspicious.png",
    [
        "Quickfix Supplies Co.",
        "",
        "Invoice #: INV-9981",
        "Date: 2027-01-05",  # future-dated — should get flagged
        "Bill To: Fiasco Consultancy",
        "",
        "Description              Qty    Unit Price    Amount",
        "Office supplies           1     KES 12,000    KES 12,000",
        "Delivery                  1     KES 3,000     KES 3,000",
        "",
        "Subtotal:                              KES 15,000",
        "VAT (16%):                             KES 2,400",
        "Total:                                 KES 25,000",  # doesn't match subtotal+VAT — should get flagged
        "",
        "Payment due: 2026-09-10",
    ],
    title="RECEIPT",
)

print("\nDone. Run: python demo.py sample_documents/invoice_clean.png")
