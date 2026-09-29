"""
Real persistence layer using SQLite — a proper database instead of a JSON
file. This is what you swap in when moving from "demo on my laptop" to
"running for a real client."

SQLite is a single file (no server to install or pay for), which is the
right amount of infrastructure for one client. If a client later needs
multiple people hitting this at once from different machines/servers,
swap this for Postgres — the function signatures below would stay the
same, only the connection code changes.
"""

import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "data" / "documents.db"
DB_PATH.parent.mkdir(exist_ok=True)


@contextmanager
def _connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Creates the table if it doesn't exist yet. Safe to call every startup."""
    with _connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT,
                vendor_or_issuer TEXT,
                document_date TEXT,
                total REAL,
                currency TEXT,
                extraction_confidence TEXT,
                flags_json TEXT,
                extracted_json TEXT,
                processed_at TEXT NOT NULL
            )
        """)
        # Index for fast duplicate-invoice lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_invoice_number
            ON processed_documents (invoice_number)
        """)


def has_seen_invoice(invoice_number: str) -> bool:
    """True if this invoice number has been processed before."""
    if not invoice_number:
        return False
    with _connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_documents WHERE invoice_number = ? LIMIT 1",
            (invoice_number,),
        ).fetchone()
        return row is not None


def record_document(extracted: dict, flags: list[str]):
    """Saves a processed document's full record to the database."""
    with _connection() as conn:
        conn.execute(
            """
            INSERT INTO processed_documents
                (invoice_number, vendor_or_issuer, document_date, total,
                 currency, extraction_confidence, flags_json, extracted_json, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                extracted.get("invoice_number"),
                extracted.get("vendor_or_issuer"),
                extracted.get("date"),
                extracted.get("total"),
                extracted.get("currency"),
                extracted.get("extraction_confidence"),
                json.dumps(flags),
                json.dumps(extracted),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_all_documents(limit: int = 100) -> list[dict]:
    """Returns the most recently processed documents, newest first."""
    with _connection() as conn:
        rows = conn.execute(
            "SELECT * FROM processed_documents ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


# Initialize on import so any module that imports db.py has a ready table
init_db()
