"""
Invoice numbering.

Tax and non-tax invoices are separate legal series:

    Tax      : PREFIX-YYYY-0001, PREFIX-YYYY-0002, ...
    Non-tax  : PREFIX-NT-YYYY-0001, PREFIX-NT-YYYY-0002, ...

The prefix comes from the domain profile when set, otherwise the General
Settings "invoice_prefix", then the GST settings prefix, then "INV".

Counters live in invoice_number_sequences and are locked while a number is
allocated, so two simultaneous invoice creations cannot receive the same
number.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

IST = ZoneInfo("Asia/Kolkata")
PREFIX_MAX_LENGTH = 17  # PREFIX-NT-YYYY-0001 must fit the VARCHAR(30) column


def invoice_kind(invoice_type) -> str:
    """Return the counter kind for an InvoiceType value/enum."""
    value = str(getattr(invoice_type, "value", invoice_type) or "").upper()
    return "NONTAX" if value == "NON_GST" else "TAX"


def clean_invoice_prefix(value: Optional[str], fallback: str = "INV") -> str:
    """Normalise an admin-entered prefix to the characters we allow."""
    cleaned = re.sub(r"[^A-Z0-9]", "", (value or "").upper())
    return (cleaned or fallback)[:PREFIX_MAX_LENGTH]


def format_invoice_number(prefix: str, year: int, kind: str, sequence: int) -> str:
    prefix = clean_invoice_prefix(prefix)
    middle = "-NT" if kind == "NONTAX" else ""
    return f"{prefix}{middle}-{year}-{sequence:04d}"


def _invoice_year(when: Optional[datetime]) -> int:
    value = when or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(IST).year


async def resolve_invoice_prefix(
    db: AsyncSession,
    domain_id: Optional[UUID | str] = None,
    overridden: Optional[str] = None,
) -> str:
    if overridden:
        return clean_invoice_prefix(overridden)

    if domain_id:
        prefix = (await db.execute(
            text("""
                SELECT invoice_prefix
                FROM domain_profiles
                WHERE domain_id = :domain_id
                LIMIT 1
            """),
            {"domain_id": str(domain_id)},
        )).scalar_one_or_none()
        if prefix:
            return clean_invoice_prefix(prefix)

    prefix = (await db.execute(
        text("""
            SELECT value
            FROM system_settings
            WHERE "group" = 'general' AND key = 'invoice_prefix'
            LIMIT 1
        """)
    )).scalar_one_or_none()
    if prefix:
        return clean_invoice_prefix(prefix)

    prefix = (await db.execute(
        text("SELECT invoice_prefix FROM gst_settings LIMIT 1")
    )).scalar_one_or_none()
    return clean_invoice_prefix(prefix)


async def generate_invoice_number(
    db: AsyncSession,
    invoice_type,
    domain_id: Optional[UUID | str] = None,
    when: Optional[datetime] = None,
    prefix_override: Optional[str] = None,
) -> str:
    """
    Allocate the next number for this invoice's type/prefix/year.

    Must be called inside the same transaction that inserts the invoice. The
    sequence row stays locked until that transaction commits, serialising
    concurrent invoice creation.
    """
    kind = invoice_kind(invoice_type)
    year = _invoice_year(when)
    prefix = await resolve_invoice_prefix(db, domain_id, prefix_override)
    series_key = f"{prefix}|{year}|{kind}"
    number_prefix = f"{prefix}-NT" if kind == "NONTAX" else prefix

    # Create the counter on first use. ON CONFLICT DO NOTHING makes concurrent
    # first-use calls safe; the SELECT ... FOR UPDATE below then serialises them.
    await db.execute(
        text("""
            INSERT INTO invoice_number_sequences
                (id, series_key, prefix, invoice_year, invoice_kind, last_number,
                 created_at, updated_at, is_active)
            VALUES
                (:id, :series_key, :prefix, :invoice_year, :invoice_kind, 0,
                 now(), now(), true)
            ON CONFLICT (series_key) DO NOTHING
        """),
        {
            "id": str(uuid4()),
            "series_key": series_key,
            "prefix": prefix,
            "invoice_year": year,
            "invoice_kind": kind,
        },
    )

    last_number = (await db.execute(
        text("""
            SELECT last_number
            FROM invoice_number_sequences
            WHERE series_key = :series_key
            FOR UPDATE
        """),
        {"series_key": series_key},
    )).scalar_one()

    # Also account for canonical numbers already in the invoices table (for
    # example after the VPS repair script has run, or on an older deployment
    # where the counter table was added later).
    existing_numbers = (await db.execute(
        text("""
            SELECT invoice_number
            FROM invoices
            WHERE invoice_number LIKE :pattern
        """),
        {"pattern": f"{number_prefix}-{year}-%"},
    )).scalars().all()
    pattern = re.compile(rf"^{re.escape(number_prefix)}-{year}-(\d+)$")
    highest_existing = max(
        (int(match.group(1)) for number in existing_numbers
         if (match := pattern.match(number or ""))),
        default=0,
    )

    next_number = max(int(last_number or 0), highest_existing) + 1
    await db.execute(
        text("""
            UPDATE invoice_number_sequences
            SET last_number = :next_number, updated_at = now()
            WHERE series_key = :series_key
        """),
        {"next_number": next_number, "series_key": series_key},
    )

    return format_invoice_number(prefix, year, kind, next_number)
