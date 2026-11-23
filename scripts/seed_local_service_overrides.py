"""Seed per-domain service overrides (image + SEO copy) for local development.

For every service linked to the local domains, creates a
`domain_service_overrides` row pointing at a generated branded image in that
website's `public/images/services/` folder and fills domain-specific SEO copy:

    meta_title / meta_description / meta_keywords
    og_title / og_description / og_image_url

Only EMPTY fields are filled, so Admin Dashboard edits are never overwritten.

Run AFTER `scripts.seed_local_catalog`:
    PYTHONIOENCODING=utf-8 PYTHONUTF8=1 venv/Scripts/python -m scripts.seed_local_service_overrides
"""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.domain import Domain, DomainService, DomainServiceOverride
from app.models.service import Service

SITES = {
    "palei-solutions": {
        "brand": "Palei Solutions",
        "origin": "https://paleisolutions.com",
    },
    "palei-ac-service": {
        "brand": "Palei AC Service",
        "origin": "https://paleiacservice.com",
    },
}


def image_key(service_name: str) -> str:
    lower = service_name.lower()
    if "conditioner" in lower or lower.startswith("ac "):
        return "ac-services"
    if "refrigerator" in lower:
        return "refrigeration"
    if "washing" in lower:
        return "laundry"
    return "water-heating"


def seo_values(service: Service, brand: str, origin: str) -> dict:
    key = image_key(service.name)
    name = service.name
    desc = service.description or f"Professional {name.lower()} at your doorstep."
    return {
        "image_url": f"/images/services/{key}.png",
        "thumbnail_url": f"/images/services/{key}.png",
        "meta_title": f"{name} in Bhubaneswar | {brand}",
        "meta_description": (
            f"Book {name} in Bhubaneswar, Cuttack, Puri and Berhampur with {brand}. "
            f"{desc} Doorstep service, verified technicians and transparent pricing."
        ),
        "meta_keywords": (
            f"{name}, {name} Bhubaneswar, {name} Cuttack, "
            f"{name} Puri, home appliance repair, {brand}"
        ),
        "og_title": f"{name} | {brand}",
        "og_description": (
            f"{desc} Book doorstep {name.lower()} across Bhubaneswar, Cuttack, "
            f"Puri and Berhampur."
        ),
        "og_image_url": f"{origin}/images/services/{key}.png",
    }


async def main() -> None:
    created = 0
    filled_total = 0
    async with AsyncSessionLocal() as session:
        for slug, cfg in SITES.items():
            domain = (await session.execute(
                select(Domain).where(Domain.slug == slug)
            )).scalar_one_or_none()
            if not domain:
                raise SystemExit(
                    f"Domain '{slug}' not found — run scripts.seed_local_domains first"
                )

            rows = (await session.execute(
                select(DomainService, Service)
                .join(Service, Service.id == DomainService.service_id)
                .where(
                    DomainService.domain_id == domain.id,
                    DomainService.is_active == True,  # noqa: E712
                )
            )).all()

            for link, service in rows:
                override = (await session.execute(
                    select(DomainServiceOverride).where(
                        DomainServiceOverride.domain_service_id == link.id
                    )
                )).scalar_one_or_none()
                if not override:
                    override = DomainServiceOverride(domain_service_id=link.id)
                    session.add(override)
                    await session.flush()
                    created += 1

                for field, value in seo_values(service, cfg["brand"], cfg["origin"]).items():
                    if value and not getattr(override, field):
                        setattr(override, field, value)
                        filled_total += 1
            print(f"[OK] {slug}: {len(rows)} linked service(s) processed")

        await session.commit()
        print(f"[DONE] {created} override(s) created, {filled_total} field(s) filled")


if __name__ == "__main__":
    asyncio.run(main())
