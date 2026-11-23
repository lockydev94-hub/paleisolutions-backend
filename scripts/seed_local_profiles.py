"""Fill the local Palei Solutions domain profiles (idempotent).

Populates support contact, office address and social links so both websites'
headers, footers, contact sections and LocalBusiness schema render from the DB.

Only EMPTY fields are filled — existing Admin Dashboard values are never
overwritten. Re-running is therefore safe.

Contact values for Palei AC Service come from its own
`src/lib/seo-fallback.ts`. The Palei Solutions phone/address reuse the same
office and the social URLs are brand-slug placeholders (no verified handles in
the repo) — replace them in Admin Dashboard -> Domains -> Profile for
production.

Run AFTER `scripts.seed_local_domains`:
    PYTHONIOENCODING=utf-8 PYTHONUTF8=1 venv/Scripts/python -m scripts.seed_local_profiles
"""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.domain import Domain, DomainProfile

PROFILES = {
    "palei-solutions": {
        "support_phone": "+91 94377 39550",
        "whatsapp_number": "9437739550",
        "support_email": "support@paleisolutions.com",
        "office_address": "Gothapatana Square",
        "office_city": "Bhubaneswar",
        "office_state": "Odisha",
        "office_pincode": "751003",
        "office_country": "India",
        "facebook_url": "https://www.facebook.com/paleisolutions",
        "instagram_url": "https://www.instagram.com/paleisolutions",
        "youtube_url": "https://www.youtube.com/@paleisolutions",
        "linkedin_url": "https://www.linkedin.com/company/paleisolutions",
    },
    "palei-ac-service": {
        "support_phone": "+91 94377 39550",
        "whatsapp_number": "9437739550",
        "support_email": "support@paleiacservice.com",
        "office_address": "Gothapatana Square",
        "office_city": "Bhubaneswar",
        "office_state": "Odisha",
        "office_pincode": "751003",
        "office_country": "India",
        "facebook_url": "https://www.facebook.com/paleiacservice",
        "instagram_url": "https://www.instagram.com/paleiacservice",
        "youtube_url": "https://www.youtube.com/@paleiacservice",
        "linkedin_url": "https://www.linkedin.com/company/paleiacservice",
    },
}


async def main() -> None:
    filled_total = 0
    async with AsyncSessionLocal() as session:
        for slug, values in PROFILES.items():
            domain = (await session.execute(
                select(Domain).where(Domain.slug == slug)
            )).scalar_one_or_none()
            if not domain:
                raise SystemExit(
                    f"Domain '{slug}' not found — run scripts.seed_local_domains first"
                )

            profile = (await session.execute(
                select(DomainProfile).where(DomainProfile.domain_id == domain.id)
            )).scalar_one_or_none()
            if not profile:
                profile = DomainProfile(domain_id=domain.id)
                session.add(profile)
                await session.flush()

            filled = 0
            for field, value in values.items():
                if value and not getattr(profile, field):
                    setattr(profile, field, value)
                    filled += 1
            filled_total += filled
            print(f"[OK] {slug}: filled {filled} empty profile field(s)")

        await session.commit()
        print(f"[DONE] {filled_total} profile field(s) filled")


if __name__ == "__main__":
    asyncio.run(main())
