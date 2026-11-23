"""Seed a small bookable catalog for the local Palei Solutions domains.

Creates service categories, services and cities, then links them to the
`palei-solutions` and `palei-ac-service` domains so both websites' service
grids, city pickers and booking flows use database data instead of bundled
fallbacks. The AC-only site gets only the AC category; the main site gets the
full home-appliance catalog.

Safe to re-run: rows are matched by name (and by category for services) and
existing rows/links are left untouched, so Admin Dashboard edits survive.

Run AFTER `scripts.seed_local_domains`:
    PYTHONIOENCODING=utf-8 PYTHONUTF8=1 venv/Scripts/python -m scripts.seed_local_catalog
"""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.city import City
from app.models.domain import Domain, DomainCategory, DomainCity, DomainService
from app.models.service import Service, ServiceCategory

CATEGORIES = [
    {"name": "AC Services", "icon": "❄️", "sort_order": 0,
     "description": "Installation, service and repair for all AC brands"},
    {"name": "Refrigeration", "icon": "🧊", "sort_order": 1,
     "description": "Refrigerator repair for every model"},
    {"name": "Laundry", "icon": "🧺", "sort_order": 2,
     "description": "Washing machine repair and servicing"},
    {"name": "Water Heating", "icon": "🚿", "sort_order": 3,
     "description": "Geyser and water heater repair"},
]

SERVICES = [
    {"category": "AC Services", "name": "Air Conditioner Repair",
     "description": "Installation, service & repair for all AC brands",
     "base_price": 499, "duration_mins": 60, "sort_order": 0, "featured": True},
    {"category": "AC Services", "name": "AC Installation",
     "description": "Professional split & window AC installation",
     "base_price": 999, "duration_mins": 90, "sort_order": 1, "featured": False},
    {"category": "AC Services", "name": "AC Gas Refill",
     "description": "R22, R32 & R410A gas charging",
     "base_price": 1299, "duration_mins": 60, "sort_order": 2, "featured": False},
    {"category": "AC Services", "name": "AC Deep Cleaning",
     "description": "Jet cleaning for better cooling and efficiency",
     "base_price": 699, "duration_mins": 75, "sort_order": 3, "featured": False},
    {"category": "Refrigeration", "name": "Refrigerator Repair",
     "description": "Single door, double door & side-by-side models",
     "base_price": 399, "duration_mins": 60, "sort_order": 0, "featured": True},
    {"category": "Laundry", "name": "Washing Machine Repair",
     "description": "Front load & top load washing machines",
     "base_price": 399, "duration_mins": 60, "sort_order": 0, "featured": False},
    {"category": "Water Heating", "name": "Geyser Repair",
     "description": "Electric & gas water heater repair",
     "base_price": 299, "duration_mins": 45, "sort_order": 0, "featured": False},
]

CITIES = [
    {"name": "Bhubaneswar", "state": "Odisha", "sort_order": 0,
     "latitude": 20.2961, "longitude": 85.8245},
    {"name": "Cuttack", "state": "Odisha", "sort_order": 1,
     "latitude": 20.4625, "longitude": 85.8830},
    {"name": "Puri", "state": "Odisha", "sort_order": 2,
     "latitude": 19.8135, "longitude": 85.8312},
    {"name": "Berhampur", "state": "Odisha", "sort_order": 3,
     "latitude": 19.3150, "longitude": 84.7941},
]

# palei-solutions is the full home-appliance brand; palei-ac-service is AC-only.
DOMAIN_CATALOG = {
    "palei-solutions": [
        "AC Services", "Refrigeration", "Laundry", "Water Heating",
    ],
    "palei-ac-service": [
        "AC Services",
    ],
}


async def main() -> None:
    async with AsyncSessionLocal() as session:
        # ── Cities ──────────────────────────────────────────────
        cities: dict[str, City] = {}
        city_created = 0
        for spec in CITIES:
            city = (await session.execute(
                select(City).where(City.name == spec["name"])
            )).scalar_one_or_none()
            if not city:
                city = City(
                    name=spec["name"],
                    state=spec["state"],
                    base_travel_charge=0.0,
                    sort_order=spec["sort_order"],
                    latitude=spec["latitude"],
                    longitude=spec["longitude"],
                    is_serviceable=True,
                )
                session.add(city)
                await session.flush()
                city_created += 1
            cities[city.name] = city

        # ── Categories ──────────────────────────────────────────
        categories: dict[str, ServiceCategory] = {}
        cat_created = 0
        for spec in CATEGORIES:
            category = (await session.execute(
                select(ServiceCategory).where(ServiceCategory.name == spec["name"])
            )).scalar_one_or_none()
            if not category:
                category = ServiceCategory(
                    name=spec["name"],
                    description=spec["description"],
                    icon=spec["icon"],
                    sort_order=spec["sort_order"],
                )
                session.add(category)
                await session.flush()
                cat_created += 1
            categories[category.name] = category

        # ── Services ────────────────────────────────────────────
        services: dict[tuple[str, str], Service] = {}
        svc_created = 0
        for spec in SERVICES:
            category = categories[spec["category"]]
            service = (await session.execute(
                select(Service).where(
                    Service.category_id == category.id,
                    Service.name == spec["name"],
                )
            )).scalar_one_or_none()
            if not service:
                service = Service(
                    category_id=category.id,
                    name=spec["name"],
                    description=spec["description"],
                    base_price=spec["base_price"],
                    gst_percent=18.0,
                    duration_mins=spec["duration_mins"],
                    is_visible=True,
                    sort_order=spec["sort_order"],
                )
                session.add(service)
                await session.flush()
                svc_created += 1
            services[(spec["category"], spec["name"])] = service

        # ── Link catalog to each local domain ───────────────────
        link_counts = {"categories": 0, "services": 0, "cities": 0}
        for slug, category_names in DOMAIN_CATALOG.items():
            domain = (await session.execute(
                select(Domain).where(Domain.slug == slug)
            )).scalar_one_or_none()
            if not domain:
                raise SystemExit(
                    f"Domain '{slug}' not found — run scripts.seed_local_domains first"
                )

            for order, cat_name in enumerate(category_names):
                category = categories[cat_name]
                existing = (await session.execute(
                    select(DomainCategory).where(
                        DomainCategory.domain_id == domain.id,
                        DomainCategory.category_id == category.id,
                    )
                )).scalar_one_or_none()
                if not existing:
                    session.add(DomainCategory(
                        domain_id=domain.id,
                        category_id=category.id,
                        sort_order=order,
                    ))
                    link_counts["categories"] += 1

                for spec in SERVICES:
                    if spec["category"] != cat_name:
                        continue
                    service = services[(cat_name, spec["name"])]
                    linked = (await session.execute(
                        select(DomainService).where(
                            DomainService.domain_id == domain.id,
                            DomainService.service_id == service.id,
                        )
                    )).scalar_one_or_none()
                    if not linked:
                        session.add(DomainService(
                            domain_id=domain.id,
                            service_id=service.id,
                            is_featured=spec["featured"],
                        ))
                        link_counts["services"] += 1

            for order, city in enumerate(cities.values()):
                linked = (await session.execute(
                    select(DomainCity).where(
                        DomainCity.domain_id == domain.id,
                        DomainCity.city_id == city.id,
                    )
                )).scalar_one_or_none()
                if not linked:
                    session.add(DomainCity(
                        domain_id=domain.id,
                        city_id=city.id,
                        sort_order=order,
                    ))
                    link_counts["cities"] += 1

        await session.commit()
        print(
            f"[DONE] created {cat_created} categories, {svc_created} services, "
            f"{city_created} cities; linked {link_counts['categories']} categories, "
            f"{link_counts['services']} services, {link_counts['cities']} cities"
        )


if __name__ == "__main__":
    asyncio.run(main())
