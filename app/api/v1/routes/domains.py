"""
Domain Management Module — /api/v1/domains

Docs spec:
  GET    /domains                           list domains
  POST   /domains                           create domain
  GET    /domains/{id}                      domain details + stats
  PUT    /domains/{id}                      update domain
  DELETE /domains/{id}                      deactivate domain
  GET    /domains/{id}/services             list services linked to domain
  POST   /domains/{id}/services             link service to domain
  DELETE /domains/{id}/services/{ds_id}     unlink service from domain
  GET    /domains/{id}/categories           list categories linked to domain
  POST   /domains/{id}/categories           link category to domain
  DELETE /domains/{id}/categories/{dc_id}   unlink category from domain
  GET    /domains/{id}/cities               list cities linked to domain
  POST   /domains/{id}/cities               link city to domain
  DELETE /domains/{id}/cities/{dc_id}       unlink city from domain
  GET    /domains/{id}/seo                  SEO settings
  PUT    /domains/{id}/seo                  update SEO settings
  GET    /domains/{id}/legal                list legal pages
  GET    /domains/{id}/legal/{page_key}     one legal page (privacy|terms|refund-policy)
  PUT    /domains/{id}/legal/{page_key}     upsert legal page
  POST   /domains/{id}/legal/reset          restore default legal template(s)

NOTE: /domains/services/{id}/city-prices routes REMOVED — they belong
      in /services/{id}/city-prices (services.py) to avoid route conflict.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.models.domain import Domain, DomainCategory, DomainService, DomainCity, DomainSeo, DomainServiceOverride
from app.models.service import Service, ServiceCategory
from app.models.city import City
from app.api.deps import AdminOnly, AnyAuthenticated
from app.utils.response import success_response, iso

router = APIRouter()

# ── Schemas ───────────────────────────────────────────────────
class CreateDomainRequest(BaseModel):
    name:          str
    slug:          str
    description:   Optional[str] = None
    logo_url:      Optional[str] = None
    primary_color: Optional[str] = "#1B4FD8"
    meta_title:    Optional[str] = None
    meta_desc:     Optional[str] = None
    sort_order:    int = 0

class UpdateDomainRequest(BaseModel):
    name:          Optional[str] = None
    slug:          Optional[str] = None
    description:   Optional[str] = None
    logo_url:      Optional[str] = None
    primary_color: Optional[str] = None
    meta_title:    Optional[str] = None
    meta_desc:     Optional[str] = None
    sort_order:    Optional[int] = None
    is_active:     Optional[bool] = None

class LinkServiceRequest(BaseModel):
    service_id:  str
    is_featured: bool = False

class LinkCategoryRequest(BaseModel):
    category_id: str
    sort_order:  int = 0

class LinkCityRequest(BaseModel):
    city_id:    str
    sort_order: int = 0

class BulkLinkRequest(BaseModel):
    service_ids: list

class SeoRequest(BaseModel):
    meta_title:       Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords:    Optional[str] = None
    og_title:         Optional[str] = None
    og_description:   Optional[str] = None
    og_image_url:     Optional[str] = None
    canonical_url:    Optional[str] = None
    robots:           Optional[str] = "index,follow"
    schema_json:      Optional[str] = None

# ── Helpers ───────────────────────────────────────────────────
def _domain_row(d: Domain, service_count: int = 0, category_count: int = 0, city_count: int = 0) -> dict:
    return {
        "id":            str(d.id),
        "name":          d.name,
        "slug":          d.slug,
        "description":   d.description,
        "logo_url":      d.logo_url,
        "primary_color": d.primary_color,
        "meta_title":    d.meta_title,
        "meta_desc":     d.meta_desc,
        "sort_order":    d.sort_order,
        "is_active":     d.is_active,
        "service_count": service_count,
        "category_count":category_count,
        "city_count":    city_count,
        "created_at":    iso(d.created_at) if d.created_at else None,
    }

# ══════════════════════════════════════════════════════════════
# ROUTES — static paths before parameterised paths
# ══════════════════════════════════════════════════════════════

# ── List domains ──────────────────────────────────────────────
@router.get("", summary="List domains [Public]")
async def list_domains(db: AsyncSession = Depends(get_db)):
    domains = (await db.execute(
        select(Domain).where(Domain.is_active == True).order_by(Domain.sort_order)
    )).scalars().all()

    result = []
    for d in domains:
        svc_count = (await db.execute(
            select(func.count(DomainService.id))
            .where(DomainService.domain_id == d.id, DomainService.is_active == True)
        )).scalar_one()
        cat_count = (await db.execute(
            select(func.count(DomainCategory.id))
            .where(DomainCategory.domain_id == d.id, DomainCategory.is_active == True)
        )).scalar_one()
        city_count = (await db.execute(
            select(func.count(DomainCity.id))
            .where(DomainCity.domain_id == d.id, DomainCity.is_active == True)
        )).scalar_one()
        result.append(_domain_row(d, svc_count, cat_count, city_count))

    return success_response(data={"items": result, "total": len(result)})

# ── Create domain ─────────────────────────────────────────────
@router.post("", summary="Create domain [Admin]")
async def create_domain(
    payload: CreateDomainRequest,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    existing = (await db.execute(
        select(Domain).where(Domain.slug == payload.slug)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Domain slug already exists")

    domain = Domain(**payload.model_dump())
    db.add(domain)
    await db.flush()
    # Auto-create empty SEO row
    db.add(DomainSeo(domain_id=domain.id))
    await db.commit()

    return success_response(
        data=_domain_row(domain),
        message="Domain created"
    )

# ── Get domain detail ─────────────────────────────────────────
@router.get("/{domain_id}", summary="Domain details + stats [Public]")
async def get_domain(domain_id: UUID, db: AsyncSession = Depends(get_db)):
    d = (await db.execute(
        select(Domain).where(Domain.id == domain_id)
    )).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")

    svc_count = (await db.execute(
        select(func.count(DomainService.id))
        .where(DomainService.domain_id == domain_id, DomainService.is_active == True)
    )).scalar_one()
    cat_count = (await db.execute(
        select(func.count(DomainCategory.id))
        .where(DomainCategory.domain_id == domain_id, DomainCategory.is_active == True)
    )).scalar_one()
    city_count = (await db.execute(
        select(func.count(DomainCity.id))
        .where(DomainCity.domain_id == domain_id, DomainCity.is_active == True)
    )).scalar_one()

    return success_response(data=_domain_row(d, svc_count, cat_count, city_count))

# ── Update domain ─────────────────────────────────────────────
@router.put("/{domain_id}", summary="Update domain [Admin]")
async def update_domain(
    domain_id: UUID,
    payload:   UpdateDomainRequest,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    d = (await db.execute(select(Domain).where(Domain.id == domain_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    # Slug uniqueness check if slug is being changed
    if payload.slug and payload.slug != d.slug:
        clash = (await db.execute(
            select(Domain).where(Domain.slug == payload.slug, Domain.id != domain_id)
        )).scalar_one_or_none()
        if clash:
            raise HTTPException(status_code=400, detail="Slug already in use by another domain")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(d, k, v)
    await db.commit()
    return success_response(data=_domain_row(d), message="Domain updated")

# ── Deactivate domain ─────────────────────────────────────────
@router.delete("/{domain_id}", summary="Deactivate domain [Admin]")
async def deactivate_domain(
    domain_id: UUID,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    d = (await db.execute(select(Domain).where(Domain.id == domain_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    d.is_active = False
    await db.commit()
    return success_response(message="Domain deactivated")

# ── Domain services ───────────────────────────────────────────
@router.get("/{domain_id}/services", summary="Services linked to domain [Public]")
async def get_domain_services(
    domain_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    # Single JOIN query — no N+1. LEFT JOINs the per-domain override so the
    # storefront grid can show the admin-uploaded service image without a
    # separate round trip per card (the override row may not exist yet for
    # every linked service, hence outerjoin + nullable columns below).
    rows = (await db.execute(
        select(
            DomainService, Service, ServiceCategory.name.label("cat_name"),
            DomainServiceOverride.image_url.label("override_image"),
            DomainServiceOverride.thumbnail_url.label("override_thumb"),
        )
        .join(Service, Service.id == DomainService.service_id)
        .join(ServiceCategory, ServiceCategory.id == Service.category_id)
        .outerjoin(DomainServiceOverride, DomainServiceOverride.domain_service_id == DomainService.id)
        .where(
            DomainService.domain_id == domain_id,
            DomainService.is_active == True,
            Service.is_active == True,
        )
        .order_by(ServiceCategory.sort_order, Service.sort_order)
    )).all()

    return success_response(data=[{
        "domain_service_id": str(r.DomainService.id),
        "service_id":        str(r.Service.id),
        "name":              r.Service.name,
        "description":       r.Service.description,
        "category_id":       str(r.Service.category_id),
        "category_name":     r.cat_name,
        "base_price":        r.Service.base_price,
        "gst_percent":       r.Service.gst_percent,
        "duration_mins":     r.Service.duration_mins,
        "is_featured":       r.DomainService.is_featured,
        "is_visible":        r.Service.is_visible,
        "image_url":         r.override_image,
        "thumbnail_url":     r.override_thumb,
    } for r in rows])

@router.post("/{domain_id}/services", summary="Link service to domain [Admin]")
async def add_domain_service(
    domain_id: UUID,
    payload:   LinkServiceRequest,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    svc = (await db.execute(
        select(Service).where(Service.id == UUID(payload.service_id), Service.is_active == True)
    )).scalar_one_or_none()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    existing = (await db.execute(
        select(DomainService).where(
            DomainService.domain_id  == domain_id,
            DomainService.service_id == UUID(payload.service_id),
        )
    )).scalar_one_or_none()

    if existing:
        existing.is_active  = True
        existing.is_featured = payload.is_featured
        msg = "Service re-linked to domain"
    else:
        existing = DomainService(
            domain_id  = domain_id,
            service_id = UUID(payload.service_id),
            is_featured = payload.is_featured,
        )
        db.add(existing)
        msg = "Service linked to domain"

    await db.commit()
    return success_response(
        data={"domain_service_id": str(existing.id), "service_id": str(existing.service_id)},
        message=msg
    )

@router.patch("/{domain_id}/services/{ds_id}", summary="Toggle featured on linked service [Admin]")
async def toggle_featured(
    domain_id: UUID,
    ds_id:     UUID,
    payload:   dict = None,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    ds = (await db.execute(
        select(DomainService).where(DomainService.id == ds_id, DomainService.domain_id == domain_id)
    )).scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Link not found")
    ds.is_featured = not ds.is_featured
    await db.commit()
    return success_response(
        data={"domain_service_id": str(ds.id), "is_featured": ds.is_featured},
        message="Featured toggled"
    )

@router.delete("/{domain_id}/services/{ds_id}", summary="Unlink service from domain [Admin]")
async def remove_domain_service(
    domain_id: UUID,
    ds_id:     UUID,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    ds = (await db.execute(
        select(DomainService).where(DomainService.id == ds_id, DomainService.domain_id == domain_id)
    )).scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Link not found")
    ds.is_active = False
    await db.commit()
    return success_response(message="Service removed from domain")

# ── Domain categories ─────────────────────────────────────────


@router.post("/{domain_id}/services/bulk", summary="Bulk link services to domain [Admin]")
async def bulk_add_domain_services(
    domain_id: UUID,
    payload:   "BulkLinkRequest",
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    """Link multiple services to a domain in one request."""
    linked = []
    skipped = []
    for service_id in payload.service_ids:
        svc = (await db.execute(
            select(Service).where(Service.id == UUID(service_id), Service.is_active == True)
        )).scalar_one_or_none()
        if not svc:
            skipped.append(service_id)
            continue
        existing = (await db.execute(
            select(DomainService).where(
                DomainService.domain_id  == domain_id,
                DomainService.service_id == UUID(service_id),
            )
        )).scalar_one_or_none()
        if existing:
            existing.is_active = True
        else:
            db.add(DomainService(domain_id=domain_id, service_id=UUID(service_id), is_featured=False))
        linked.append(service_id)
    await db.commit()
    return success_response(
        data={"linked": len(linked), "skipped": len(skipped)},
        message=f"{len(linked)} service(s) linked to domain"
    )

@router.get("/{domain_id}/categories", summary="Categories linked to domain [Public]")
async def get_domain_categories(domain_id: UUID, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(DomainCategory, ServiceCategory)
        .join(ServiceCategory, ServiceCategory.id == DomainCategory.category_id)
        .where(
            DomainCategory.domain_id == domain_id,
            DomainCategory.is_active == True,
            ServiceCategory.is_active == True,
        )
        .order_by(DomainCategory.sort_order, ServiceCategory.sort_order)
    )).all()

    return success_response(data=[{
        "domain_category_id": str(r.DomainCategory.id),
        "category_id":        str(r.ServiceCategory.id),
        "name":               r.ServiceCategory.name,
        "description":        r.ServiceCategory.description,
        "icon":               r.ServiceCategory.icon,
        "sort_order":         r.DomainCategory.sort_order,
    } for r in rows])

@router.post("/{domain_id}/categories", summary="Link category to domain [Admin]")
async def add_domain_category(
    domain_id: UUID,
    payload:   LinkCategoryRequest,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    cat = (await db.execute(
        select(ServiceCategory).where(ServiceCategory.id == UUID(payload.category_id), ServiceCategory.is_active == True)
    )).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    existing = (await db.execute(
        select(DomainCategory).where(
            DomainCategory.domain_id   == domain_id,
            DomainCategory.category_id == UUID(payload.category_id),
        )
    )).scalar_one_or_none()

    if existing:
        existing.is_active  = True
        existing.sort_order = payload.sort_order
        msg = "Category re-linked"
    else:
        existing = DomainCategory(
            domain_id   = domain_id,
            category_id = UUID(payload.category_id),
            sort_order  = payload.sort_order,
        )
        db.add(existing)
        msg = "Category linked to domain"

    await db.commit()
    return success_response(
        data={"domain_category_id": str(existing.id), "category_id": str(existing.category_id)},
        message=msg
    )

@router.delete("/{domain_id}/categories/{dc_id}", summary="Unlink category from domain [Admin]")
async def remove_domain_category(
    domain_id: UUID,
    dc_id:     UUID,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    dc = (await db.execute(
        select(DomainCategory).where(DomainCategory.id == dc_id, DomainCategory.domain_id == domain_id)
    )).scalar_one_or_none()
    if not dc:
        raise HTTPException(status_code=404, detail="Link not found")
    dc.is_active = False
    await db.commit()
    return success_response(message="Category removed from domain")

# ── Cities linked to domain ─────────────────────────────────────
@router.get("/{domain_id}/cities", summary="Cities linked to domain [Public]")
async def get_domain_cities(domain_id: UUID, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(DomainCity, City)
        .join(City, City.id == DomainCity.city_id)
        .where(
            DomainCity.domain_id == domain_id,
            DomainCity.is_active == True,
            City.is_active == True,
        )
        .order_by(DomainCity.sort_order, City.sort_order)
    )).all()

    return success_response(data=[{
        "domain_city_id": str(r.DomainCity.id),
        "city_id":        str(r.City.id),
        "name":           r.City.name,
        "state":          r.City.state,
        "is_serviceable": getattr(r.City, "is_serviceable", True),
        "sort_order":     r.DomainCity.sort_order,
    } for r in rows])

@router.post("/{domain_id}/cities", summary="Link city to domain [Admin]")
async def add_domain_city(
    domain_id: UUID,
    payload:   LinkCityRequest,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    city = (await db.execute(
        select(City).where(City.id == UUID(payload.city_id), City.is_active == True)
    )).scalar_one_or_none()
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    existing = (await db.execute(
        select(DomainCity).where(
            DomainCity.domain_id == domain_id,
            DomainCity.city_id   == UUID(payload.city_id),
        )
    )).scalar_one_or_none()

    if existing:
        existing.is_active  = True
        existing.sort_order = payload.sort_order
        msg = "City re-linked"
    else:
        existing = DomainCity(
            domain_id  = domain_id,
            city_id    = UUID(payload.city_id),
            sort_order = payload.sort_order,
        )
        db.add(existing)
        msg = "City linked to domain"

    await db.commit()
    return success_response(
        data={"domain_city_id": str(existing.id), "city_id": str(existing.city_id)},
        message=msg
    )

@router.delete("/{domain_id}/cities/{dc_id}", summary="Unlink city from domain [Admin]")
async def remove_domain_city(
    domain_id: UUID,
    dc_id:     UUID,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    dc = (await db.execute(
        select(DomainCity).where(DomainCity.id == dc_id, DomainCity.domain_id == domain_id)
    )).scalar_one_or_none()
    if not dc:
        raise HTTPException(status_code=404, detail="Link not found")
    dc.is_active = False
    await db.commit()
    return success_response(message="City removed from domain")

# ── SEO settings ──────────────────────────────────────────────
@router.get("/{domain_id}/seo", summary="Domain SEO settings [Admin]")
async def get_domain_seo(domain_id: UUID, db: AsyncSession = Depends(get_db)):
    seo = (await db.execute(
        select(DomainSeo).where(DomainSeo.domain_id == domain_id, DomainSeo.is_active == True)
    )).scalar_one_or_none()
    if not seo:
        # Auto-create on first access
        seo = DomainSeo(domain_id=domain_id)
        db.add(seo); await db.commit()
    return success_response(data={
        "id":              str(seo.id),
        "domain_id":       str(seo.domain_id),
        "meta_title":      seo.meta_title,
        "meta_description":seo.meta_description,
        "meta_keywords":   seo.meta_keywords,
        "og_title":        seo.og_title,
        "og_description":  seo.og_description,
        "og_image_url":    seo.og_image_url,
        "canonical_url":   seo.canonical_url,
        "robots":          seo.robots,
        "schema_json":     seo.schema_json,
    })

@router.put("/{domain_id}/seo", summary="Update domain SEO settings [Admin]")
async def update_domain_seo(
    domain_id: UUID,
    payload:   SeoRequest,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    seo = (await db.execute(
        select(DomainSeo).where(DomainSeo.domain_id == domain_id)
    )).scalar_one_or_none()
    if not seo:
        seo = DomainSeo(domain_id=domain_id)
        db.add(seo)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(seo, k, v)
    await db.commit()
    return success_response(message="SEO settings updated")


# ══════════════════════════════════════════════════════════════
# DOMAIN PROFILE — rich branding, social, address, invoice data
# ══════════════════════════════════════════════════════════════
from app.models.domain import DomainProfile as _DomainProfile

class DomainProfileRequest(BaseModel):
    # Media
    logo_url:           Optional[str] = None
    logo_dark_url:      Optional[str] = None
    favicon_url:        Optional[str] = None
    og_image_url:       Optional[str] = None
    banner_url:         Optional[str] = None
    # Social
    facebook_url:       Optional[str] = None
    instagram_url:      Optional[str] = None
    twitter_url:        Optional[str] = None
    youtube_url:        Optional[str] = None
    linkedin_url:       Optional[str] = None
    whatsapp_number:    Optional[str] = None
    # Contact
    support_phone:      Optional[str] = None
    support_email:      Optional[str] = None
    office_address:     Optional[str] = None
    office_city:        Optional[str] = None
    office_state:       Optional[str] = None
    office_pincode:     Optional[str] = None
    office_country:     Optional[str] = None
    google_maps_url:    Optional[str] = None
    # Invoice / business
    business_legal_name:  Optional[str] = None
    gstin:                Optional[str] = None
    pan_number:           Optional[str] = None
    invoice_prefix:       Optional[str] = None
    bank_account_name:    Optional[str] = None
    bank_account_number:  Optional[str] = None
    bank_ifsc:            Optional[str] = None
    bank_name:            Optional[str] = None
    bank_branch:          Optional[str] = None
    upi_id:               Optional[str] = None
    # About
    tagline:              Optional[str] = None
    about_short:          Optional[str] = None
    copyright_text:       Optional[str] = None


def _profile_row(p: _DomainProfile) -> dict:
    return {
        "id": str(p.id), "domain_id": str(p.domain_id),
        # media
        "logo_url": p.logo_url, "logo_dark_url": p.logo_dark_url,
        "favicon_url": p.favicon_url, "og_image_url": p.og_image_url,
        "banner_url": p.banner_url,
        # social
        "facebook_url": p.facebook_url, "instagram_url": p.instagram_url,
        "twitter_url": p.twitter_url, "youtube_url": p.youtube_url,
        "linkedin_url": p.linkedin_url, "whatsapp_number": p.whatsapp_number,
        # contact
        "support_phone": p.support_phone, "support_email": p.support_email,
        "office_address": p.office_address, "office_city": p.office_city,
        "office_state": p.office_state, "office_pincode": p.office_pincode,
        "office_country": p.office_country, "google_maps_url": p.google_maps_url,
        # invoice
        "business_legal_name": p.business_legal_name, "gstin": p.gstin,
        "pan_number": p.pan_number, "invoice_prefix": p.invoice_prefix,
        "bank_account_name": p.bank_account_name, "bank_account_number": p.bank_account_number,
        "bank_ifsc": p.bank_ifsc, "bank_name": p.bank_name, "bank_branch": p.bank_branch,
        "upi_id": p.upi_id,
        # about
        "tagline": p.tagline, "about_short": p.about_short, "copyright_text": p.copyright_text,
    }


@router.get("/{domain_id}/profile", summary="Domain profile [Public]")
async def get_domain_profile(domain_id: UUID, db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(
        select(_DomainProfile).where(_DomainProfile.domain_id == domain_id)
    )).scalar_one_or_none()
    if not profile:
        # Auto-create empty profile on first access
        profile = _DomainProfile(domain_id=domain_id)
        db.add(profile)
        await db.commit()
    return success_response(data=_profile_row(profile))


@router.put("/{domain_id}/profile", summary="Update domain profile [Admin]")
async def update_domain_profile(
    domain_id: UUID,
    payload: DomainProfileRequest,
    current_user=Depends(AdminOnly),
    db: AsyncSession = Depends(get_db),
):
    profile = (await db.execute(
        select(_DomainProfile).where(_DomainProfile.domain_id == domain_id)
    )).scalar_one_or_none()
    if not profile:
        profile = _DomainProfile(domain_id=domain_id)
        db.add(profile)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(profile, k, v)
    await db.commit()
    return success_response(data=_profile_row(profile), message="Domain profile updated")


# ══════════════════════════════════════════════════════════════
# DOMAIN SERVICE OVERRIDES — per-domain image + SEO per service
# ══════════════════════════════════════════════════════════════
from app.models.domain import DomainServiceOverride

class DomainServiceOverrideRequest(BaseModel):
    image_url:        Optional[str] = None
    thumbnail_url:    Optional[str] = None
    meta_title:       Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords:    Optional[str] = None
    og_title:         Optional[str] = None
    og_description:   Optional[str] = None
    og_image_url:     Optional[str] = None
    # canonical_url, robots, schema_json are auto-generated by the frontend
    includes_json:    Optional[str] = None   # JSON array of strings
    excludes_json:    Optional[str] = None   # JSON array of strings
    faqs_json:        Optional[str] = None   # JSON array of {q, a} objects


def _override_row(o: DomainServiceOverride) -> dict:
    import json
    def _json_list(v):
        if not v: return []
        try: return json.loads(v)
        except: return []
    def _json_faqs(v):
        if not v: return []
        try: return json.loads(v)
        except: return []
    return {
        "id":               str(o.id),
        "domain_service_id":str(o.domain_service_id),
        "image_url":        o.image_url,
        "thumbnail_url":    o.thumbnail_url,
        "meta_title":       o.meta_title,
        "meta_description": o.meta_description,
        "meta_keywords":    o.meta_keywords,
        "og_title":         o.og_title,
        "og_description":   o.og_description,
        "og_image_url":     o.og_image_url,
        "includes":         _json_list(o.includes_json),
        "excludes":         _json_list(o.excludes_json),
        "faqs":             _json_faqs(o.faqs_json),
    }


@router.get("/{domain_id}/services/{ds_id}/override",
            summary="Get domain-service override (image + SEO) [Admin]")
async def get_domain_service_override(
    domain_id: UUID,
    ds_id:     UUID,
    db: AsyncSession = Depends(get_db),
):
    # Validate the domain_service belongs to this domain
    ds = (await db.execute(
        select(DomainService).where(
            DomainService.id == ds_id,
            DomainService.domain_id == domain_id,
        )
    )).scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Domain service link not found")

    override = (await db.execute(
        select(DomainServiceOverride).where(DomainServiceOverride.domain_service_id == ds_id)
    )).scalar_one_or_none()

    if not override:
        # Return empty shell — no auto-create on GET
        return success_response(data={
            "id": None, "domain_service_id": str(ds_id),
            "image_url": None, "thumbnail_url": None,
            "meta_title": None, "meta_description": None, "meta_keywords": None,
            "og_title": None, "og_description": None, "og_image_url": None,
            "includes": [], "excludes": [], "faqs": [],
        })

    return success_response(data=_override_row(override))


@router.put("/{domain_id}/services/{ds_id}/override",
            summary="Upsert domain-service override (image + SEO) [Admin]")
async def upsert_domain_service_override(
    domain_id: UUID,
    ds_id:     UUID,
    payload:   DomainServiceOverrideRequest,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db),
):
    ds = (await db.execute(
        select(DomainService).where(
            DomainService.id == ds_id,
            DomainService.domain_id == domain_id,
        )
    )).scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Domain service link not found")

    override = (await db.execute(
        select(DomainServiceOverride).where(DomainServiceOverride.domain_service_id == ds_id)
    )).scalar_one_or_none()

    if not override:
        override = DomainServiceOverride(domain_service_id=ds_id)
        db.add(override)

    import json as _json
    payload_dict = payload.model_dump()
    for k, v in payload_dict.items():
        setattr(override, k, v)

    await db.commit()
    await db.refresh(override)
    return success_response(data=_override_row(override), message="Override saved")


# ── Bulk override download (generate JSON template) ───────────
class BulkOverrideDownloadRequest(BaseModel):
    service_ids: list[str]  # list of domain_service_ids to include


@router.post("/{domain_id}/services/overrides/download",
             summary="Generate bulk override JSON template [Admin]")
async def bulk_override_download(
    domain_id: UUID,
    payload:   BulkOverrideDownloadRequest,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a JSON array of override objects for the requested domain_service_ids.
    Services that already have override data will have those values populated;
    services without overrides will have empty/null fields ready to fill.
    """
    import json as _json

    result = []
    for ds_id_str in payload.service_ids:
        try:
            ds_id = UUID(ds_id_str)
        except Exception:
            continue

        row = (await db.execute(
            select(DomainService, Service)
            .join(Service, Service.id == DomainService.service_id)
            .where(
                DomainService.id == ds_id,
                DomainService.domain_id == domain_id,
                DomainService.is_active == True,
            )
        )).first()
        if not row:
            continue

        ds, svc = row

        override = (await db.execute(
            select(DomainServiceOverride).where(DomainServiceOverride.domain_service_id == ds_id)
        )).scalar_one_or_none()

        def _jlist(v):
            if not v: return []
            try: return _json.loads(v)
            except: return []

        cat = (await db.execute(
            select(ServiceCategory).where(ServiceCategory.id == svc.category_id)
        )).scalar_one_or_none()

        entry = {
            "domain_service_id":     str(ds_id),
            "service_id":            str(svc.id),
            "service_name":          svc.name,
            "category_name":         cat.name if cat else None,
            "has_existing_override": override is not None,
            "meta_title":            override.meta_title       if override else None,
            "meta_description":      override.meta_description if override else None,
            "meta_keywords":         override.meta_keywords     if override else None,
            "og_title":              override.og_title          if override else None,
            "og_description":        override.og_description    if override else None,
            "og_image_url":          override.og_image_url      if override else None,
            "includes":              _jlist(override.includes_json if override else None),
            "excludes":              _jlist(override.excludes_json if override else None),
            "faqs":                  _jlist(override.faqs_json     if override else None),
        }
        result.append(entry)

    return success_response(data=result, message=f"{len(result)} service override(s) exported")


# ── Bulk override upload (apply JSON template) ────────────────
class BulkOverrideItem(BaseModel):
    domain_service_id: str
    meta_title:        Optional[str] = None
    meta_description:  Optional[str] = None
    meta_keywords:     Optional[str] = None
    og_title:          Optional[str] = None
    og_description:    Optional[str] = None
    og_image_url:      Optional[str] = None
    includes:          list = []
    excludes:          list = []
    faqs:              list = []

class BulkOverrideUploadRequest(BaseModel):
    overrides: list[BulkOverrideItem]


@router.post("/{domain_id}/services/overrides/upload",
             summary="Bulk upsert service overrides (SEO + Content only) [Admin]")
async def bulk_override_upload(
    domain_id: UUID,
    payload:   BulkOverrideUploadRequest,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db),
):
    """
    Accepts a list of override objects and upserts SEO + Content fields.
    Does NOT touch image_url / thumbnail_url (those are uploaded per service manually).
    """
    import json as _json

    updated = 0
    skipped = 0
    errors  = []

    for item in payload.overrides:
        try:
            ds_id = UUID(item.domain_service_id)
        except Exception:
            errors.append(f"Invalid UUID: {item.domain_service_id}")
            skipped += 1
            continue

        ds = (await db.execute(
            select(DomainService).where(
                DomainService.id == ds_id,
                DomainService.domain_id == domain_id,
                DomainService.is_active == True,
            )
        )).scalar_one_or_none()

        if not ds:
            errors.append(f"Domain service link not found: {item.domain_service_id}")
            skipped += 1
            continue

        override = (await db.execute(
            select(DomainServiceOverride).where(DomainServiceOverride.domain_service_id == ds_id)
        )).scalar_one_or_none()

        if not override:
            override = DomainServiceOverride(domain_service_id=ds_id)
            db.add(override)

        override.meta_title       = item.meta_title
        override.meta_description = item.meta_description
        override.meta_keywords    = item.meta_keywords
        override.og_title         = item.og_title
        override.og_description   = item.og_description
        override.og_image_url     = item.og_image_url
        override.includes_json    = _json.dumps(item.includes or [])
        override.excludes_json    = _json.dumps(item.excludes or [])
        override.faqs_json        = _json.dumps(item.faqs     or [])

        updated += 1

    await db.commit()

    return success_response(
        data={"updated": updated, "skipped": skipped, "errors": errors},
        message=f"{updated} override(s) saved successfully"
    )


# ══════════════════════════════════════════════════════════════
# DOMAIN LEGAL PAGES — privacy / terms / refund, admin-managed
#
# Google Play rejected Bibek Pro + Palei Pro (Aug 30, 2026) because the privacy
# policy did not disclose Location collection. The copy lived inside each
# Next.js site, so a policy fix meant editing and redeploying every site. It is
# now DB-backed: the websites render GET /legal/{page_key} (public) and admins
# edit it from Admin Dashboard → Domains → Legal.
#
#   GET    /domains/{id}/legal                 list pages (published only unless ?all=true)
#   GET    /domains/{id}/legal/{page_key}      one page  [Public]
#   PUT    /domains/{id}/legal/{page_key}      upsert    [Admin]
#   POST   /domains/{id}/legal/reset           restore default template(s) [Admin]
# ══════════════════════════════════════════════════════════════
import json as _legal_json

from app.models.domain import DomainLegalPage
from app.services.legal_content import (
    LEGAL_PAGE_KEYS,
    LEGAL_PAGE_LABELS,
    build_context as _legal_ctx,
    build_legal_page as _legal_template,
)


class LegalSection(BaseModel):
    id:      str
    title:   str
    content: str


class LegalPageRequest(BaseModel):
    title:            Optional[str] = None
    subtitle:         Optional[str] = None
    sections:         Optional[list[LegalSection]] = None
    footer_note:      Optional[str] = None
    effective_date:   Optional[str] = None
    meta_title:       Optional[str] = None
    meta_description: Optional[str] = None
    robots:           Optional[str] = None
    is_published:     Optional[bool] = None


class LegalResetRequest(BaseModel):
    # None / empty → reset every known page for this domain
    page_keys: Optional[list[str]] = None


def _legal_row(p: DomainLegalPage, *, is_default: Optional[bool] = None) -> dict:
    try:
        sections = _legal_json.loads(p.sections_json) if p.sections_json else []
    except Exception:
        sections = []
    row = {
        "id":               str(p.id),
        "domain_id":        str(p.domain_id),
        "page_key":         p.page_key,
        "label":            LEGAL_PAGE_LABELS.get(p.page_key, p.page_key),
        "title":            p.title,
        "subtitle":         p.subtitle,
        "sections":         sections,
        "footer_note":      p.footer_note,
        "effective_date":   p.effective_date,
        "meta_title":       p.meta_title,
        "meta_description": p.meta_description,
        "robots":           p.robots or "index,follow",
        "is_published":     bool(p.is_published),
        "updated_at":       iso(p.updated_at),
    }
    if is_default is not None:
        row["is_default"] = is_default
    return row


def _legal_fingerprint(title, subtitle, sections, footer_note) -> str:
    """
    Cheap equality key for "is this still the untouched default template?".
    Only the fields an admin actually edits in the Legal tab are compared —
    effective_date and the meta fields are ignored so a small SEO tweak does not
    make the page look customised.
    """
    return _legal_json.dumps(
        [title or "", subtitle or "", sections or [], footer_note or ""],
        ensure_ascii=False, sort_keys=True,
    )


async def build_legal_ctx_for_domain(domain: Domain, db: AsyncSession) -> dict:
    """
    Assemble the interpolation context for the default legal templates from the
    domain row + its profile, so the SAME backend image deployed twice on the
    VPS (Bibek Enterprises / Palei Solutions) renders brand-correct policies.
    Shared with the startup seeder in app/main.py.
    """
    profile = (await db.execute(
        select(_DomainProfile).where(_DomainProfile.domain_id == domain.id)
    )).scalar_one_or_none()

    address = ", ".join(filter(None, [
        getattr(profile, "office_address", None),
        getattr(profile, "office_city", None),
        getattr(profile, "office_state", None),
        getattr(profile, "office_pincode", None),
    ])) if profile else ""

    return _legal_ctx(
        site_name=domain.name,
        legal_name=getattr(profile, "business_legal_name", None) or domain.name,
        support_email=getattr(profile, "support_email", None) or f"support@{domain.slug}.com",
        support_phone=getattr(profile, "support_phone", None),
        address=address or None,
        gstin=getattr(profile, "gstin", None),
    )


async def _get_domain_or_404(domain_id: UUID, db: AsyncSession) -> Domain:
    domain = (await db.execute(select(Domain).where(Domain.id == domain_id))).scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return domain


@router.get("/{domain_id}/legal", summary="List domain legal pages [Public]")
async def list_domain_legal_pages(
    domain_id: UUID,
    include_unpublished: bool = Query(False, alias="all"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(DomainLegalPage).where(DomainLegalPage.domain_id == domain_id)
    if not include_unpublished:
        stmt = stmt.where(DomainLegalPage.is_published == True)  # noqa: E712
    rows = (await db.execute(stmt)).scalars().all()

    # Stable display order: known keys first (privacy, terms, refund-policy),
    # anything custom appended alphabetically.
    order = {k: i for i, k in enumerate(LEGAL_PAGE_KEYS)}
    rows = sorted(rows, key=lambda r: (order.get(r.page_key, 99), r.page_key))

    # Flag pages still identical to the seeded template, so the admin can tell at
    # a glance which policies have actually been reviewed for this brand.
    defaults: dict[str, str] = {}
    if rows:
        try:
            domain = await _get_domain_or_404(domain_id, db)
            ctx = await build_legal_ctx_for_domain(domain, db)
            for key in {r.page_key for r in rows}:
                tpl = _legal_template(key, ctx)
                if tpl:
                    defaults[key] = _legal_fingerprint(
                        tpl.get("title"), tpl.get("subtitle"),
                        tpl.get("sections"), tpl.get("footer_note"),
                    )
        except Exception:
            defaults = {}   # badge is cosmetic — never fail the list because of it

    def _is_default(r: DomainLegalPage) -> Optional[bool]:
        expected = defaults.get(r.page_key)
        if expected is None:
            return None
        try:
            sections = _legal_json.loads(r.sections_json) if r.sections_json else []
        except Exception:
            sections = []
        return _legal_fingerprint(r.title, r.subtitle, sections, r.footer_note) == expected

    return success_response(data=[_legal_row(r, is_default=_is_default(r)) for r in rows])


@router.get("/{domain_id}/legal/{page_key}", summary="Get one legal page [Public]")
async def get_domain_legal_page(
    domain_id: UUID,
    page_key:  str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public — the websites SSR/ISR-fetch this for /privacy, /terms and
    /refund-policy. If the domain has no row yet (fresh VPS database, before the
    startup seeder has run) we render the default template on the fly rather
    than 404ing, because a blank privacy-policy URL is exactly what got the apps
    rejected. Nothing is written here; GET stays side-effect free.
    """
    page = (await db.execute(
        select(DomainLegalPage).where(
            DomainLegalPage.domain_id == domain_id,
            DomainLegalPage.page_key == page_key,
        )
    )).scalar_one_or_none()

    if page:
        return success_response(data=_legal_row(page))

    domain = await _get_domain_or_404(domain_id, db)
    ctx = await build_legal_ctx_for_domain(domain, db)
    tpl = _legal_template(page_key, ctx)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Unknown legal page '{page_key}'")

    return success_response(
        data={
            "id":        None,
            "domain_id": str(domain_id),
            "label":     LEGAL_PAGE_LABELS.get(page_key, page_key),
            "updated_at": None,
            "is_default": True,   # not yet persisted — admin has not customised it
            **tpl,
        },
        message="Default template (not yet saved for this domain)",
    )


@router.put("/{domain_id}/legal/{page_key}", summary="Upsert a legal page [Admin]")
async def upsert_domain_legal_page(
    domain_id: UUID,
    page_key:  str,
    payload:   LegalPageRequest,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db),
):
    domain = await _get_domain_or_404(domain_id, db)

    page = (await db.execute(
        select(DomainLegalPage).where(
            DomainLegalPage.domain_id == domain_id,
            DomainLegalPage.page_key == page_key,
        )
    )).scalar_one_or_none()

    if not page:
        # Seed from the default template so a partial PUT never produces a
        # half-empty policy page.
        ctx = await build_legal_ctx_for_domain(domain, db)
        tpl = _legal_template(page_key, ctx) or {}
        page = DomainLegalPage(
            domain_id        = domain_id,
            page_key         = page_key,
            title            = tpl.get("title") or LEGAL_PAGE_LABELS.get(page_key, page_key),
            subtitle         = tpl.get("subtitle"),
            sections_json    = _legal_json.dumps(tpl.get("sections", []), ensure_ascii=False),
            footer_note      = tpl.get("footer_note"),
            effective_date   = tpl.get("effective_date"),
            meta_title       = tpl.get("meta_title"),
            meta_description = tpl.get("meta_description"),
            robots           = tpl.get("robots", "index,follow"),
            is_published     = True,
        )
        db.add(page)

    data = payload.model_dump(exclude_none=True)
    sections = data.pop("sections", None)
    if sections is not None:
        page.sections_json = _legal_json.dumps(sections, ensure_ascii=False)
    for k, v in data.items():
        setattr(page, k, v)

    await db.commit()
    await db.refresh(page)
    return success_response(data=_legal_row(page), message=f"{page.title} saved")


@router.post("/{domain_id}/legal/reset", summary="Restore default legal template(s) [Admin]")
async def reset_domain_legal_pages(
    domain_id: UUID,
    payload:   LegalResetRequest,
    current_user = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db),
):
    """
    Overwrite the stored copy with the current default template — the escape
    hatch when an edit has broken a page, or after the template itself is updated
    to satisfy a new store policy. Keeps the existing `is_published` flag.
    """
    domain = await _get_domain_or_404(domain_id, db)
    ctx = await build_legal_ctx_for_domain(domain, db)

    keys = payload.page_keys or list(LEGAL_PAGE_KEYS)
    unknown = [k for k in keys if k not in LEGAL_PAGE_KEYS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown legal page(s): {', '.join(unknown)}")

    reset: list[str] = []
    for key in keys:
        tpl = _legal_template(key, ctx)
        if not tpl:
            continue
        page = (await db.execute(
            select(DomainLegalPage).where(
                DomainLegalPage.domain_id == domain_id,
                DomainLegalPage.page_key == key,
            )
        )).scalar_one_or_none()
        if not page:
            page = DomainLegalPage(domain_id=domain_id, page_key=key, is_published=True)
            db.add(page)

        page.title            = tpl["title"]
        page.subtitle         = tpl["subtitle"]
        page.sections_json    = _legal_json.dumps(tpl["sections"], ensure_ascii=False)
        page.footer_note      = tpl["footer_note"]
        page.effective_date   = tpl["effective_date"]
        page.meta_title       = tpl["meta_title"]
        page.meta_description = tpl["meta_description"]
        page.robots           = tpl["robots"]
        reset.append(key)

    await db.commit()
    return success_response(
        data={"reset": reset},
        message=f"{len(reset)} legal page(s) restored to the default template",
    )
