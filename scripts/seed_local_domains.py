"""Seed the local Palei Solutions domain rows (idempotent).

Creates the `domains` + `domain_seo` rows the two Palei websites resolve via
NEXT_PUBLIC_DOMAIN_SLUG (palei-solutions and palei-ac-service), so the sites
render domain data from the database instead of built-in fallbacks.

Safe to re-run: existing domains are left untouched so Admin Dashboard edits
are never overwritten.

Run from the backend directory:
    PYTHONIOENCODING=utf-8 PYTHONUTF8=1 venv/Scripts/python -m scripts.seed_local_domains
"""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.domain import Domain, DomainSeo

DOMAINS = [
    {
        "name": "Palei Solutions",
        "slug": "palei-solutions",
        "description": (
            "Professional home appliance repair and maintenance services "
            "across Odisha — AC, refrigerator, washing machine, geyser, "
            "microwave and more."
        ),
        "primary_color": "#0A2463",
        "meta_title": "Palei Solutions — Home Appliance Repair & Service",
        "meta_desc": (
            "Professional home appliance repair and maintenance services. "
            "AC, Refrigerator, Washing Machine, Geyser, Microwave & more — "
            "at your doorstep."
        ),
        "sort_order": 0,
    },
    {
        "name": "Palei AC Service",
        "slug": "palei-ac-service",
        "description": (
            "Expert AC repair, installation, gas refill, deep cleaning and "
            "AMC services in Bhubaneswar and across Odisha."
        ),
        "primary_color": "#1565C0",
        "meta_title": "Palei AC Service — AC Repair & Installation in Bhubaneswar",
        "meta_desc": (
            "Professional AC repair, installation, gas refill & deep cleaning "
            "in Bhubaneswar & Odisha. Split AC, Window AC, Cassette AC — "
            "same-day doorstep service."
        ),
        "sort_order": 1,
    },
]


async def main() -> None:
    created = 0
    async with AsyncSessionLocal() as session:
        for data in DOMAINS:
            existing = (await session.execute(
                select(Domain).where(Domain.slug == data["slug"])
            )).scalar_one_or_none()
            if existing:
                print(f"[SKIP] Domain already exists: {existing.slug}")
                continue

            domain = Domain(**data)
            session.add(domain)
            await session.flush()
            session.add(DomainSeo(domain_id=domain.id))
            created += 1
            print(f"[OK] Domain created: {domain.slug}")

        if created:
            await session.commit()
        print(f"[DONE] {created} domain(s) created, {len(DOMAINS) - created} skipped")


if __name__ == "__main__":
    asyncio.run(main())
