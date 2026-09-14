"""
Faculty profile endpoints — CRUD, search, identifiers.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.faculty import FacultyProfile, FacultyIdentifier, FacultyNameVariant

router = APIRouter()


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

    # Get total count
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


@router.get("/{faculty_id}")
async def get_faculty(faculty_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single faculty profile with all details."""
    query = (
        select(FacultyProfile)
        .options(
            selectinload(FacultyProfile.identifiers),
            selectinload(FacultyProfile.name_variants),
            selectinload(FacultyProfile.metric_snapshots),
        )
        .where(FacultyProfile.id == faculty_id)
    )
    result = await db.execute(query)
    faculty = result.scalar_one_or_none()

    if not faculty:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Faculty not found")

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
        "research_interests": faculty.research_interests,
        "education": faculty.education,
        "academic_experience": faculty.academic_experience,
        "awards": faculty.awards,
        "memberships": faculty.memberships,
        "teaching_engagements": faculty.teaching_engagements,
        "declared_publication_count": faculty.declared_publication_count,
        "status": faculty.status,
        "identifiers": [
            {
                "id": str(ident.id),
                "type": ident.identifier_type,
                "value": ident.identifier_value,
                "verified": ident.verified,
                "confidence": ident.confidence,
                "verification_source": ident.verification_source,
            }
            for ident in faculty.identifiers
        ],
        "name_variants": [
            {
                "variant": nv.name_variant,
                "source": nv.variant_source,
                "confirmed": nv.is_confirmed,
            }
            for nv in faculty.name_variants
        ],
        "metric_snapshots": [
            {
                "h_index": ms.h_index,
                "i10_index": ms.i10_index,
                "total_citations": ms.total_citations,
                "total_publications": ms.total_publications,
                "snapshot_date": ms.snapshot_date.isoformat(),
            }
            for ms in faculty.metric_snapshots
        ],
    }
