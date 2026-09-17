import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db, async_session_factory
from app.models.faculty import FacultyProfile, FacultyIdentifier, FacultyNameVariant
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.services.identity_verification_service import IdentityVerificationService
from app.agents.discovery_agent import PublicationDiscoveryAgent
from app.agents.deduplication_agent import DeduplicationAgent
from app.agents.attribution_agent import FacultyAttributionAgent
from app.agents.metrics_agent import MetricsAgent

logger = logging.getLogger(__name__)


async def _async_background_faculty_sync(faculty_id: UUID):
    """Non-blocking background worker to discover new works, dedup, and update metrics."""
    try:
        async with async_session_factory() as bg_session:
            discovery = PublicationDiscoveryAgent(bg_session)
            await discovery.run()

            dedup = DeduplicationAgent(bg_session)
            await dedup.run()

            attrib = FacultyAttributionAgent(bg_session)
            await attrib.run()

            metrics = MetricsAgent(bg_session)
            await metrics.run()
    except Exception as exc:
        logger.warning(f"Background faculty sync failed for {faculty_id}: {exc}")

router = APIRouter()


class IdentifierInput(BaseModel):
    type: str
    value: str


class SaveIdentifiersRequest(BaseModel):
    identifiers: List[IdentifierInput]


def check_faculty_permission(faculty_id: UUID, current_user: User):
    """Ensure faculty can only modify their own profile, while admins have global access."""
    if current_user.role in ("admin", "research_admin", "dept_admin", "super_admin"):
        return True
    if current_user.faculty_id and str(current_user.faculty_id) == str(faculty_id):
        return True
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: You are not authorized to modify another faculty member's identifiers.",
    )


def _build_faculty_response(faculty: FacultyProfile, db: AsyncSession) -> Dict[str, Any]:
    """Helper to assemble a rich FacultyProfile payload."""
    confirmed_pubs = []
    source_systems = set()
    for link in (faculty.publication_links or []):
        p = link.publication
        if p:
            for s in (p.sources or []):
                if s.source_system:
                    source_systems.add(s.source_system)
            confirmed_pubs.append({
                "id": str(p.id),
                "title": p.title,
                "doi": p.doi,
                "year": p.year,
                "citation_count": p.citation_count or 0,
                "venue": p.journal_name or p.conference_name or p.publisher,
                "authors_raw": p.authors_raw,
                "sources": [
                    {"system": s.source_system, "source_id": s.source_id, "url": s.source_url}
                    for s in (p.sources or [])
                ],
            })

    confirmed_pubs.sort(key=lambda x: (x.get("year") or 0, x.get("citation_count") or 0), reverse=True)

    service = IdentityVerificationService(db)
    idents_response = []
    for ident in (faculty.identifiers or []):
        norm_val, profile_url = service.normalize_identifier(ident.identifier_type, ident.identifier_value)
        idents_response.append({
            "id": str(ident.id),
            "type": ident.identifier_type,
            "value": ident.identifier_value,
            "profile_url": profile_url,
            "verified": ident.verified,
            "confidence": ident.confidence or 1.0,
            "verification_source": ident.verification_source,
            "verified_at": ident.verified_at.isoformat() if ident.verified_at else None,
            "created_at": ident.created_at.isoformat() if ident.created_at else None,
        })

    latest_snapshot = faculty.metric_snapshots[-1] if faculty.metric_snapshots else None

    return {
        "id": str(faculty.id),
        "raw_name": faculty.raw_name,
        "normalized_name": faculty.normalized_name,
        "title_prefix": faculty.title_prefix,
        "first_name": faculty.first_name,
        "last_name": faculty.last_name,
        "department": faculty.department,
        "designation": faculty.designation,
        "institutional_email": faculty.institutional_email,
        "phone": faculty.phone,
        "research_interests": faculty.research_interests or [],
        "education": faculty.education,
        "academic_experience": faculty.academic_experience,
        "awards": faculty.awards,
        "memberships": faculty.memberships,
        "teaching_engagements": faculty.teaching_engagements,
        "declared_publication_count": faculty.declared_publication_count,
        "status": faculty.status,
        "identifiers": idents_response,
        "name_variants": [
            {
                "variant": nv.name_variant,
                "source": nv.variant_source,
                "confirmed": nv.is_confirmed,
            }
            for nv in (faculty.name_variants or [])
        ],
        "metric_snapshot": {
            "h_index": latest_snapshot.h_index if latest_snapshot else 0,
            "i10_index": latest_snapshot.i10_index if latest_snapshot else 0,
            "total_citations": latest_snapshot.total_citations if latest_snapshot else 0,
            "total_publications": latest_snapshot.total_publications if latest_snapshot else len(confirmed_pubs),
            "snapshot_date": latest_snapshot.snapshot_date.isoformat() if latest_snapshot else None,
        } if latest_snapshot else None,
        "contributing_sources": sorted(list(source_systems)),
        "confirmed_publications_count": len(confirmed_pubs),
        "recent_publications": confirmed_pubs[:10],
    }


@router.get("/")
async def list_faculty(
    department: Optional[str] = Query(None, description="Filter by department"),
    search: Optional[str] = Query(None, description="Search by name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List faculty profiles with optional filtering."""
    query = select(FacultyProfile).options(
        selectinload(FacultyProfile.identifiers),
        selectinload(FacultyProfile.name_variants),
    )

    if department:
        query = query.where(FacultyProfile.department == department.upper())
    if search:
        query = query.where(
            FacultyProfile.normalized_name.ilike(f"%{search.lower()}%")
        )

    query = query.order_by(FacultyProfile.raw_name).offset(skip).limit(limit)
    result = await db.execute(query)
    faculty_list = result.scalars().all()

    count_query = select(func.count(FacultyProfile.id))
    if department:
        count_query = count_query.where(FacultyProfile.department == department.upper())
    if search:
        count_query = count_query.where(
            FacultyProfile.normalized_name.ilike(f"%{search.lower()}%")
        )
    total = (await db.execute(count_query)).scalar()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": [
            {
                "id": str(f.id),
                "raw_name": f.raw_name,
                "normalized_name": f.normalized_name,
                "title_prefix": f.title_prefix,
                "first_name": f.first_name,
                "last_name": f.last_name,
                "department": f.department,
                "designation": f.designation,
                "institutional_email": f.institutional_email,
                "research_interests": f.research_interests,
                "status": f.status,
                "declared_publication_count": f.declared_publication_count,
                "identifiers": [
                    {
                        "type": ident.identifier_type,
                        "value": ident.identifier_value,
                        "verified": ident.verified,
                    }
                    for ident in f.identifiers
                ],
                "name_variants": [nv.name_variant for nv in f.name_variants],
            }
            for f in faculty_list
        ],
    }


@router.get("/departments")
async def list_departments(db: AsyncSession = Depends(get_db)):
    """List all departments with faculty counts."""
    query = (
        select(FacultyProfile.department, func.count(FacultyProfile.id))
        .where(FacultyProfile.department.isnot(None))
        .group_by(FacultyProfile.department)
        .order_by(FacultyProfile.department)
    )
    result = await db.execute(query)
    departments = result.all()
    return {
        "departments": [
            {"name": dept, "faculty_count": count}
            for dept, count in departments
        ]
    }


@router.get("/stats")
async def faculty_stats(db: AsyncSession = Depends(get_db)):
    """Get summary statistics for faculty profiles."""
    total = (await db.execute(select(func.count(FacultyProfile.id)))).scalar()
    with_identifiers = (
        await db.execute(
            select(func.count(func.distinct(FacultyIdentifier.faculty_id)))
        )
    ).scalar()

    return {
        "total_faculty": total,
        "with_external_identifiers": with_identifiers,
        "without_identifiers": total - (with_identifiers or 0),
    }


# ==============================================================================
# AUTHENTICATED CURRENT FACULTY ROUTES (/me)
# ==============================================================================

async def _resolve_authenticated_faculty(current_user: User, db: AsyncSession) -> Optional[FacultyProfile]:
    faculty = None
    if current_user.faculty_id:
        query = (
            select(FacultyProfile)
            .options(
                selectinload(FacultyProfile.identifiers),
                selectinload(FacultyProfile.name_variants),
                selectinload(FacultyProfile.metric_snapshots),
                selectinload(FacultyProfile.publication_links).joinedload(PublicationAuthor.publication).selectinload(Publication.sources),
            )
            .where(FacultyProfile.id == current_user.faculty_id)
        )
        faculty = (await db.execute(query)).scalar_one_or_none()

    # Self-healing fallback by institutional email
    if not faculty and current_user.email:
        clean_email = current_user.email.strip().lower()
        query = (
            select(FacultyProfile)
            .options(
                selectinload(FacultyProfile.identifiers),
                selectinload(FacultyProfile.name_variants),
                selectinload(FacultyProfile.metric_snapshots),
                selectinload(FacultyProfile.publication_links).joinedload(PublicationAuthor.publication).selectinload(Publication.sources),
            )
            .where(
                (func.lower(FacultyProfile.institutional_email) == clean_email)
                | (func.lower(FacultyProfile.raw_email) == clean_email)
            )
        )
        faculty = (await db.execute(query)).scalar_one_or_none()
        if faculty:
            current_user.faculty_id = faculty.id
            await db.commit()

    return faculty


@router.get("/me")
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the authenticated faculty member's profile."""
    if current_user.role in ("admin", "research_admin", "super_admin") and not current_user.faculty_id:
        return {
            "admin": True,
            "user": {
                "id": str(current_user.id),
                "email": current_user.email,
                "role": current_user.role,
                "full_name": current_user.full_name,
            }
        }

    faculty = await _resolve_authenticated_faculty(current_user, db)
    if not faculty:
        raise HTTPException(
            status_code=404,
            detail="Faculty profile not found for this user account. Please contact your institutional administrator."
        )

    return _build_faculty_response(faculty, db)


@router.get("/me/identifiers")
async def get_my_identifiers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get external digital identifiers for the authenticated faculty member."""
    faculty = await _resolve_authenticated_faculty(current_user, db)
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty profile not found.")

    service = IdentityVerificationService(db)
    return await service.get_faculty_identifiers_status(faculty.id)


@router.post("/me/identifiers")
async def save_my_identifiers(
    request: SaveIdentifiersRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save & verify external identifiers for the authenticated faculty member."""
    faculty = await _resolve_authenticated_faculty(current_user, db)
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty profile not found.")

    service = IdentityVerificationService(db)
    actor = f"faculty_{current_user.email}"
    raw_data = [{"type": i.type, "value": i.value} for i in request.identifiers]

    saved_results = await service.save_faculty_identifiers(
        faculty_id=faculty.id,
        identifiers_data=raw_data,
        actor=actor,
    )
    return {
        "message": f"Successfully updated {len(saved_results)} external identifier(s).",
        "faculty_id": str(faculty.id),
        "saved_identifiers": saved_results,
    }


@router.post("/me/identifiers/{id_type}/verify")
async def reverify_my_identifier(
    id_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-verify an existing identifier for the authenticated faculty member."""
    faculty = await _resolve_authenticated_faculty(current_user, db)
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty profile not found.")

    stmt = select(FacultyIdentifier).where(
        FacultyIdentifier.faculty_id == faculty.id,
        FacultyIdentifier.identifier_type == id_type.lower().strip(),
    )
    ident = (await db.execute(stmt)).scalar_one_or_none()
    if not ident:
        raise HTTPException(status_code=404, detail=f"No saved identifier of type '{id_type}' found.")

    service = IdentityVerificationService(db)
    res = await service.save_faculty_identifiers(
        faculty_id=faculty.id,
        identifiers_data=[{"type": id_type, "value": ident.identifier_value}],
        actor=f"reverify_{current_user.email}",
    )
    return {"message": "Identifier re-verified successfully", "result": res[0] if res else None}


@router.delete("/me/identifiers/{id_type}")
async def delete_my_identifier(
    id_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect an identifier for the authenticated faculty member."""
    faculty = await _resolve_authenticated_faculty(current_user, db)
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty profile not found.")

    service = IdentityVerificationService(db)
    success = await service.delete_faculty_identifier(faculty.id, id_type)
    if not success:
        raise HTTPException(status_code=404, detail=f"No identifier of type '{id_type}' found to delete.")
    return {"message": f"Identifier '{id_type}' removed successfully."}


@router.post("/me/sync")
async def sync_my_publications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger publication sync for the authenticated faculty member."""
    faculty = await _resolve_authenticated_faculty(current_user, db)
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty profile not found.")

    discovery = PublicationDiscoveryAgent(db)
    d_stats = await discovery.run()

    dedup = DeduplicationAgent(db)
    dup_stats = await dedup.run()

    attrib = FacultyAttributionAgent(db)
    att_stats = await attrib.run()

    metrics = MetricsAgent(db)
    m_stats = await metrics.run()

    return {
        "status": "success",
        "message": "Faculty research publications synchronized from verified identifiers.",
        "summary": {
            "discovery": d_stats,
            "deduplication": dup_stats,
            "attribution": att_stats,
            "metrics": m_stats,
        },
    }


# ==============================================================================
# SPECIFIC FACULTY ID ROUTES (ADMIN & DIRECT ACCESS)
# ==============================================================================

@router.get("/{faculty_id}")
async def get_faculty(faculty_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single faculty profile with full unified research identity details."""
    query = (
        select(FacultyProfile)
        .options(
            selectinload(FacultyProfile.identifiers),
            selectinload(FacultyProfile.name_variants),
            selectinload(FacultyProfile.metric_snapshots),
            selectinload(FacultyProfile.publication_links).joinedload(PublicationAuthor.publication).selectinload(Publication.sources),
        )
        .where(FacultyProfile.id == faculty_id)
    )
    result = await db.execute(query)
    faculty = result.scalar_one_or_none()

    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty not found")

    return _build_faculty_response(faculty, db)


@router.get("/{faculty_id}/identifiers")
async def get_faculty_identifiers(
    faculty_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full external digital identifiers status for a faculty member."""
    check_faculty_permission(faculty_id, current_user)
    service = IdentityVerificationService(db)
    return await service.get_faculty_identifiers_status(faculty_id)


@router.post("/{faculty_id}/identifiers")
async def save_faculty_identifiers(
    faculty_id: UUID,
    request: SaveIdentifiersRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save & verify external identifiers for a faculty member."""
    check_faculty_permission(faculty_id, current_user)
    service = IdentityVerificationService(db)
    
    actor = f"faculty_{current_user.email}" if current_user.role == "faculty" else f"admin_{current_user.email}"
    raw_data = [{"type": i.type, "value": i.value} for i in request.identifiers]
    
    saved_results = await service.save_faculty_identifiers(
        faculty_id=faculty_id,
        identifiers_data=raw_data,
        actor=actor,
    )

    return {
        "message": f"Successfully updated {len(saved_results)} external identifier(s).",
        "faculty_id": str(faculty_id),
        "saved_identifiers": saved_results,
    }


@router.post("/{faculty_id}/identifiers/{id_type}/verify")
async def reverify_single_identifier(
    faculty_id: UUID,
    id_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-verifies an existing saved identifier."""
    check_faculty_permission(faculty_id, current_user)
    
    stmt = select(FacultyIdentifier).where(
        FacultyIdentifier.faculty_id == faculty_id,
        FacultyIdentifier.identifier_type == id_type.lower().strip(),
    )
    ident = (await db.execute(stmt)).scalar_one_or_none()
    if not ident:
        raise HTTPException(status_code=404, detail=f"No saved identifier of type '{id_type}' found.")

    service = IdentityVerificationService(db)
    actor = f"reverify_{current_user.email}"
    res = await service.save_faculty_identifiers(
        faculty_id=faculty_id,
        identifiers_data=[{"type": id_type, "value": ident.identifier_value}],
        actor=actor,
    )
    return {"message": "Identifier re-verified successfully", "result": res[0] if res else None}


@router.delete("/{faculty_id}/identifiers/{id_type}")
async def delete_faculty_identifier(
    faculty_id: UUID,
    id_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Removes a connected external researcher identifier."""
    check_faculty_permission(faculty_id, current_user)
    service = IdentityVerificationService(db)
    success = await service.delete_faculty_identifier(faculty_id, id_type)
    if not success:
        raise HTTPException(status_code=404, detail=f"No identifier of type '{id_type}' found to delete.")
    return {"message": f"Identifier '{id_type}' removed successfully."}


@router.post("/{faculty_id}/sync")
async def sync_faculty_publications(
    faculty_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Triggers automated publication discovery & processing for a faculty member."""
    check_faculty_permission(faculty_id, current_user)
    
    discovery = PublicationDiscoveryAgent(db)
    d_stats = await discovery.run()

    dedup = DeduplicationAgent(db)
    dup_stats = await dedup.run()

    attrib = FacultyAttributionAgent(db)
    att_stats = await attrib.run()

    metrics = MetricsAgent(db)
    m_stats = await metrics.run()

    return {
        "status": "success",
        "message": "Faculty research publications synchronized from verified identifiers.",
        "summary": {
            "discovery": d_stats,
            "deduplication": dup_stats,
            "attribution": att_stats,
            "metrics": m_stats,
        },
    }
