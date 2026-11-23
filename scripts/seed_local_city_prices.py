"""Seed per-city price overrides for the local service catalog (idempotent).

Creates one `service_city_prices` row per seeded service and city so the
websites' city picker shows city-specific prices instead of always using the
service's base_price.

Safe to re-run: a row is only created when the (service, city) pair has no
override yet. Existing prices are left untouched, so Admin Dashboard edits
survive.

Run AFTER `scripts.seed_local_catalog`:
    PYTHONIOENCODING=utf-8 PYTHONUTF8=1 venv/Scripts/python -m scripts.seed_local_city_prices
"""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.city import City
from app.models.domain import ServiceCityPrice
from app.models.service import Service

# Bhubaneswar is the base market; farther cities carry a small travel premium.
CITY_PRICES = {
    "Air Conditioner Repair": {
        "Bhubaneswar": 499, "Cuttack": 549, "Puri": 599, "Berhampur": 649,
    },
    "AC Installation": {
        "Bhubaneswar": 999, "Cuttack": 1099, "Puri": 1199, "Berhampur": 1299,
    },
    "AC Gas Refill": {
        "Bhubaneswar": 1299, "Cuttack": 1399, "Puri": 1499, "Berhampur": 1599,
    },
    "AC Deep Cleaning": {
        "Bhubaneswar": 699, "Cuttack": 749, "Puri": 799, "Berhampur": 849,
    },
    "Refrigerator Repair": {
        "Bhubaneswar": 399, "Cuttack": 449, "Puri": 499, "Berhampur": 549,
    },
    "Washing Machine Repair": {
        "Bhubaneswar": 399, "Cuttack": 449, "Puri": 499, "Berhampur": 549,
    },
    "Geyser Repair": {
        "Bhubaneswar": 299, "Cuttack": 349, "Puri": 399, "Berhampur": 449,
    },
}


async def main() -> None:
    created = 0
    skipped = 0
    async with AsyncSessionLocal() as session:
        cities = {
            c.name: c for c in (await session.execute(
                select(City).where(City.is_active == True)  # noqa: E712
            )).scalars().all()
        }
        services = {
            s.name: s for s in (await session.execute(
                select(Service).where(Service.is_active == True)  # noqa: E712
            )).scalars().all()
        }

        for service_name, city_prices in CITY_PRICES.items():
            service = services.get(service_name)
            if not service:
                raise SystemExit(
                    f"Service '{service_name}' not found — run scripts.seed_local_catalog first"
                )
            for city_name, price in city_prices.items():
                city = cities.get(city_name)
                if not city:
                    raise SystemExit(
                        f"City '{city_name}' not found — run scripts.seed_local_catalog first"
                    )
                existing = (await session.execute(
                    select(ServiceCityPrice).where(
                        ServiceCityPrice.service_id == service.id,
                        ServiceCityPrice.city_id == city.id,
                    )
                )).scalar_one_or_none()
                if existing:
                    skipped += 1
                    continue
                session.add(ServiceCityPrice(
                    service_id=service.id,
                    city_id=city.id,
                    price=price,
                    is_available=True,
                ))
                created += 1

        await session.commit()
        print(f"[DONE] {created} city price(s) created, {skipped} already present")


if __name__ == "__main__":
    asyncio.run(main())
