"""
Repair existing TAX invoice numbers into the canonical running series.

What it does
------------
Tax invoices (GST_B2C and GST_B2B) are renumbered in creation order:

    PREFIX-YYYY-0001, PREFIX-YYYY-0002, ...

The prefix for each invoice is resolved from its domain profile, then the
General Settings ``invoice_prefix``, then the GST settings prefix, then "INV".
Non-tax invoices are not touched; they have their own ``PREFIX-NT-YYYY-0001``
series.

Safety
------
* Dry-run is the default. Nothing is written unless ``--apply`` is passed.
* Every changed invoice is copied into ``invoice_number_repair_backup`` with
  its old number, new number and a shared run id.
* Numbers are staged to temporary values first, so swapping/renumbering cannot
  trip the UNIQUE(invoice_number) constraint.
* The sequence counters are updated to match, so the next generated invoice
  continues from the last repaired number.
* Safe to re-run: an already-correct database produces no changes.

Usage (from the backend directory, with the deployment's environment loaded)
-----------------------------------------------------------------------------
    python -m scripts.repair_invoice_numbers              # preview
    python -m scripts.repair_invoice_numbers --apply      # write
    python -m scripts.repair_invoice_numbers --apply --prefix BIBEK

On the Docker deployment:
    docker compose run --rm api python -m scripts.repair_invoice_numbers --apply
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.database import AsyncSessionLocal, engine
from app.services.invoice_numbering import (
    clean_invoice_prefix,
    format_invoice_number,
)

IST = ZoneInfo("Asia/Kolkata")


SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS invoice_number_sequences (
        id             UUID PRIMARY KEY,
        series_key     VARCHAR(80) NOT NULL UNIQUE,
        prefix         VARCHAR(20) NOT NULL,
        invoice_year   INTEGER NOT NULL,
        invoice_kind   VARCHAR(10) NOT NULL,
        last_number    INTEGER NOT NULL DEFAULT 0,
        created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        updated_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        is_active      BOOLEAN DEFAULT TRUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS invoice_number_repair_backup (
        id                 UUID PRIMARY KEY,
        invoice_id         UUID NOT NULL,
        old_invoice_number VARCHAR(50) NOT NULL,
        new_invoice_number VARCHAR(50) NOT NULL,
        run_id             UUID NOT NULL,
        repaired_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_invoice_number_repair_backup_run
        ON invoice_number_repair_backup (run_id)
    """,
)


def _year(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(IST).year


def build_repair_plan(rows, default_prefix: str, override_prefix: Optional[str] = None):
    """Return (plan, group_counters). Kept pure so the mapping is testable."""
    counters: dict[tuple[str, int], int] = {}
    plan = []

    for row in sorted(rows, key=lambda item: (item["created_at"], str(item["id"]))):
        prefix = clean_invoice_prefix(
            override_prefix or row.get("domain_prefix") or default_prefix
        )
        year = _year(row["created_at"])
        key = (prefix, year)
        counters[key] = counters.get(key, 0) + 1
        new_number = format_invoice_number(prefix, year, "TAX", counters[key])
        plan.append({
            "id": str(row["id"]),
            "old": row["invoice_number"],
            "new": new_number,
            "prefix": prefix,
            "year": year,
        })
    return plan, counters


async def _repair(apply: bool, override_prefix: Optional[str]) -> None:
    async with AsyncSessionLocal() as session:
        if apply:
            for statement in SCHEMA_SQL:
                await session.execute(text(statement))

        default_prefix = (await session.execute(
            text("""
                SELECT value
                FROM system_settings
                WHERE "group" = 'general' AND key = 'invoice_prefix'
                LIMIT 1
            """)
        )).scalar_one_or_none()
        if not default_prefix:
            default_prefix = (await session.execute(
                text("SELECT invoice_prefix FROM gst_settings LIMIT 1")
            )).scalar_one_or_none()
        default_prefix = clean_invoice_prefix(default_prefix)

        rows = (await session.execute(
            text("""
                SELECT i.id,
                       i.invoice_number,
                       i.created_at,
                       dp.invoice_prefix AS domain_prefix
                FROM invoices i
                LEFT JOIN bookings b
                       ON b.id = i.booking_id
                LEFT JOIN domain_profiles dp
                       ON dp.domain_id = COALESCE(i.domain_id, b.domain_id)
                WHERE i.invoice_type::text IN ('GST_B2C', 'GST_B2B')
                ORDER BY i.created_at ASC, i.id ASC
            """)
        )).mappings().all()

        plan, counters = build_repair_plan(rows, default_prefix, override_prefix)
        changed = [item for item in plan if item["old"] != item["new"]]

        print(f"Tax invoices found : {len(plan)}")
        print(f"Numbers to change  : {len(changed)}")
        print(f"Default prefix     : {default_prefix}")
        if override_prefix:
            print(f"Prefix override    : {clean_invoice_prefix(override_prefix)}")
        print("")

        for item in changed:
            print(f"  {item['old']:<30} -> {item['new']}")

        if not apply:
            print("\nDRY RUN — no changes written. Re-run with --apply to repair.")
            return

        run_id = str(uuid4())

        if changed:
            backup_rows = [
                {
                    "id": str(uuid4()),
                    "invoice_id": item["id"],
                    "old": item["old"][:50],
                    "new": item["new"][:50],
                    "run_id": run_id,
                }
                for item in changed
            ]
            await session.execute(
                text("""
                    INSERT INTO invoice_number_repair_backup
                        (id, invoice_id, old_invoice_number, new_invoice_number, run_id)
                    VALUES
                        (:id, :invoice_id, :old, :new, :run_id)
                """),
                backup_rows,
            )

            # Move every changed row to a unique temporary value first. This
            # avoids collisions when invoice numbers are re-ordered or swapped.
            for item in changed:
                await session.execute(
                    text("""
                        UPDATE invoices
                        SET invoice_number = :temporary, updated_at = now()
                        WHERE id = :invoice_id
                    """),
                    {
                        "temporary": "TMP" + uuid4().hex[:24],
                        "invoice_id": item["id"],
                    },
                )

            for item in changed:
                await session.execute(
                    text("""
                        UPDATE invoices
                        SET invoice_number = :new_number, updated_at = now()
                        WHERE id = :invoice_id
                    """),
                    {"new_number": item["new"], "invoice_id": item["id"]},
                )

        # If a prefix was forced, save it so future invoices continue the same
        # repaired series instead of falling back to INV.
        if override_prefix:
            saved_prefix = clean_invoice_prefix(override_prefix)
            await session.execute(
                text("""
                    INSERT INTO system_settings
                        (id, "group", key, value, is_secret, label,
                         created_at, updated_at, is_active)
                    VALUES
                        (:id, 'general', 'invoice_prefix', :prefix, false,
                         'Invoice Prefix', now(), now(), true)
                    ON CONFLICT ("group", key) DO UPDATE
                    SET value = EXCLUDED.value, updated_at = now()
                """),
                {"id": str(uuid4()), "prefix": saved_prefix},
            )

        # Keep the live counters aligned with the repaired series. GREATEST
        # means a re-run can never move an existing counter backwards.
        for (prefix, year), last_number in counters.items():
            series_key = f"{prefix}|{year}|TAX"
            await session.execute(
                text("""
                    INSERT INTO invoice_number_sequences
                        (id, series_key, prefix, invoice_year, invoice_kind,
                         last_number, created_at, updated_at, is_active)
                    VALUES
                        (:id, :series_key, :prefix, :year, 'TAX',
                         :last_number, now(), now(), true)
                    ON CONFLICT (series_key) DO UPDATE
                    SET last_number = GREATEST(
                            invoice_number_sequences.last_number,
                            EXCLUDED.last_number
                        ),
                        prefix = EXCLUDED.prefix,
                        updated_at = now()
                """),
                {
                    "id": str(uuid4()),
                    "series_key": series_key,
                    "prefix": prefix,
                    "year": year,
                    "last_number": last_number,
                },
            )

        await session.commit()
        print(f"\nAPPLIED — {len(changed)} invoice number(s) updated.")
        if override_prefix:
            print(f"General Settings invoice_prefix saved as {clean_invoice_prefix(override_prefix)}.")
        print(f"Backup run id: {run_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the repaired numbers. Without this flag the script is a dry run.",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Force one prefix for all tax invoices, e.g. BIBEK or PAL.",
    )
    args = parser.parse_args()

    async def run_and_dispose():
        try:
            await _repair(args.apply, args.prefix)
        finally:
            await engine.dispose()

    asyncio.run(run_and_dispose())


if __name__ == "__main__":
    main()
