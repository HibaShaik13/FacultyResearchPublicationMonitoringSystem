"""Analytics endpoints — citations, metrics, trends."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.publication import Publication
from app.models.faculty import FacultyProfile
from app.models.user import User
from app.api.v1.auth import get_current_user

router = APIRouter()

@router.get("/dashboard")
async def dashboard_stats(
    faculty_id: str = Query(None, description="Filter by faculty ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard-level KPIs."""
    if not faculty_id:
        total_faculty = (await db.execute(select(func.count(FacultyProfile.id)))).scalar() or 0
        total_pubs = (await db.execute(select(func.count(Publication.id)))).scalar() or 0
        verified_pubs = (
            await db.execute(
                select(func.count(Publication.id)).where(
                    Publication.verification_status.in_(["verified", "partially_verified"])
                )
            )
        ).scalar() or 0
        pending_review = (
            await db.execute(
                select(func.count(Publication.id)).where(
                    Publication.verification_status == "needs_review"
                )
            )
        ).scalar() or 0
        flagged = (
            await db.execute(
                select(func.count(Publication.id)).where(
                    Publication.risk_level.in_(["medium", "high"])
                )
            )
        ).scalar() or 0
        total_citations = (
            await db.execute(select(func.sum(Publication.citation_count)))
        ).scalar() or 0
        
        return {
            "total_faculty": total_faculty,
            "total_publications": total_pubs,
            "verified_publications": verified_pubs,
            "pending_review": pending_review,
            "flagged_records": flagged,
            "total_citations": total_citations,
        }
    else:
        # Faculty-specific dashboard
        from app.models.metrics import FacultyMetricSnapshot
        from app.models.review import ReviewTask
        from app.models.publication import PublicationAuthor
        import uuid
        
        fac_uuid = uuid.UUID(faculty_id) if isinstance(faculty_id, str) else faculty_id

        metrics_query = select(FacultyMetricSnapshot).where(FacultyMetricSnapshot.faculty_id == fac_uuid).order_by(FacultyMetricSnapshot.snapshot_date.desc()).limit(1)
        metrics = (await db.execute(metrics_query)).scalars().first()
        
        total_pubs = metrics.total_publications if metrics else 0
        total_citations = metrics.total_citations if metrics else 0
        h_index = metrics.h_index if metrics else 0
        i10_index = metrics.i10_index if metrics else 0
        
        pending_review = (await db.execute(
            select(func.count(ReviewTask.id)).where(ReviewTask.entity_id == fac_uuid)
        )).scalar() or 0
        
        # Verify pubs for faculty
        verified_pubs = (await db.execute(
            select(func.count(Publication.id))
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == fac_uuid)
            .where(Publication.verification_status.in_(["verified", "partially_verified"]))
        )).scalar() or 0
        
        flagged = (await db.execute(
            select(func.count(Publication.id))
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == fac_uuid)
            .where(Publication.risk_level.in_(["medium", "high"]))
        )).scalar() or 0

        return {
            "total_faculty": 1,
            "total_publications": total_pubs,
            "verified_publications": verified_pubs,
            "pending_review": pending_review,
            "flagged_records": flagged,
            "total_citations": total_citations,
            "h_index": h_index,
            "i10_index": i10_index
        }

@router.get("/publication-trends")
async def publication_trends(
    faculty_id: str = Query(None, description="Filter by faculty ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get publication count trends by year."""
    if faculty_id:
        import uuid
        fac_uuid = uuid.UUID(faculty_id) if isinstance(faculty_id, str) else faculty_id
        from app.models.publication import PublicationAuthor
        query = (
            select(Publication.year, func.count(Publication.id))
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == fac_uuid)
            .where(Publication.year.isnot(None))
            .group_by(Publication.year)
            .order_by(Publication.year)
        )
    else:
        query = (
            select(Publication.year, func.count(Publication.id))
            .where(Publication.year.isnot(None))
            .group_by(Publication.year)
            .order_by(Publication.year)
        )
    result = await db.execute(query)
    return {
        "trends": [
            {"year": year, "count": count}
            for year, count in result.all()
        ]
    }

@router.get("/verification-distribution")
async def verification_distribution(db: AsyncSession = Depends(get_db)):
    """Get distribution of verification statuses."""
    query = (
        select(Publication.verification_status, func.count(Publication.id))
        .group_by(Publication.verification_status)
    )
    result = await db.execute(query)
    return {
        "distribution": [
            {"status": status, "count": count}
            for status, count in result.all()
        ]
    }

@router.get("/citation-trends")
async def citation_trends(
    faculty_id: str = Query(None, description="Filter by faculty ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get real citation counts grouped by publication year."""
    import uuid
    from app.models.publication import PublicationAuthor

    if faculty_id:
        fac_uuid = uuid.UUID(faculty_id) if isinstance(faculty_id, str) else faculty_id
        query = (
            select(Publication.year, func.sum(Publication.citation_count), func.count(Publication.id))
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == fac_uuid)
            .where(Publication.year.isnot(None))
            .group_by(Publication.year)
            .order_by(Publication.year)
        )
    else:
        query = (
            select(Publication.year, func.sum(Publication.citation_count), func.count(Publication.id))
            .where(Publication.year.isnot(None))
            .group_by(Publication.year)
            .order_by(Publication.year)
        )

    result = await db.execute(query)
    trends = [
        {"year": year, "citations": citations or 0, "publications": count or 0}
        for year, citations, count in result.all()
    ]
    return {"trends": trends}


@router.get("/integrity-stats")
async def integrity_stats(
    faculty_id: str = Query(None, description="Filter by faculty ID"),
    db: AsyncSession = Depends(get_db)
):
    """Aggregate risk levels and review tasks from real database."""
    import uuid
    from app.models.publication import PublicationAuthor
    from app.models.review import ReviewTask

    if faculty_id:
        fac_uuid = uuid.UUID(faculty_id) if isinstance(faculty_id, str) else faculty_id
        query = (
            select(Publication.risk_level, func.count(Publication.id))
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == fac_uuid)
            .group_by(Publication.risk_level)
        )
        rev_count = (
            await db.execute(
                select(func.count(Publication.id))
                .join(Publication.authors)
                .where(PublicationAuthor.faculty_id == fac_uuid)
                .where(Publication.verification_status.in_(["needs_review", "rejected"]))
            )
        ).scalar() or 0
    else:
        query = select(Publication.risk_level, func.count(Publication.id)).group_by(Publication.risk_level)
        rev_count = (
            await db.execute(
                select(func.count(Publication.id)).where(
                    Publication.verification_status.in_(["needs_review", "rejected"])
                )
            )
        ).scalar() or 0

    result = await db.execute(query)
    stats = {"low": 0, "medium": 0, "high": 0, "none": 0, "review_required": rev_count}
    for level, count in result.all():
        if level in stats:
            stats[level] = count
        elif not level or level == "none":
            stats["none"] += count

    return stats


@router.get("/research-areas")
async def research_areas(
    faculty_id: Optional[str] = Query(None, description="Filter by faculty ID"),
    db: AsyncSession = Depends(get_db)
):
    """Return top research areas calculated from real faculty profile interests."""
    import json
    import uuid
    from collections import Counter

    if faculty_id:
        try:
            fac_uuid = uuid.UUID(faculty_id) if isinstance(faculty_id, str) else faculty_id
            fac = await db.get(FacultyProfile, fac_uuid)
            raw_interests = [fac.research_interests] if fac and fac.research_interests else []
        except ValueError:
            raw_interests = []
    else:
        res = await db.execute(select(FacultyProfile.research_interests))
        raw_interests = res.scalars().all()

    counts = Counter()
    for item in raw_interests:
        if not item:
            continue
        if isinstance(item, list):
            joined = "".join(item)
            try:
                parsed = json.loads(joined)
                if isinstance(parsed, list):
                    for area in parsed:
                        if isinstance(area, str) and area.strip():
                            counts[area.strip()] += 1
            except Exception:
                for chunk in item:
                    if isinstance(chunk, str) and len(chunk) > 2 and not chunk.startswith(("[", '"', "'", ",", "]")):
                        counts[chunk.strip()] += 1
        elif isinstance(item, str):
            try:
                parsed = json.loads(item)
                if isinstance(parsed, list):
                    for area in parsed:
                        if isinstance(area, str) and area.strip():
                            counts[area.strip()] += 1
            except Exception:
                if len(item) > 2:
                    counts[item.strip()] += 1

    total = sum(counts.values()) or 1
    sorted_areas = [
        {"area": area, "name": area, "count": count, "percentage": round((count / total) * 100, 1)}
        for area, count in counts.most_common(12)
    ]

    return {"areas": sorted_areas}


@router.get("/collaborations")
async def collaborations(
    department: Optional[str] = Query(None, description="Filter by department"),
    faculty_id: Optional[str] = Query(None, description="Filter by faculty ID"),
    db: AsyncSession = Depends(get_db),
):
    """Return collaboration intelligence network from real faculty profiles and research affinities."""
    import uuid
    from app.services.research_intelligence_service import ResearchIntelligenceService

    fac_uuid = None
    if faculty_id:
        try:
            fac_uuid = uuid.UUID(faculty_id)
        except ValueError:
            pass

    service = ResearchIntelligenceService(db)
    return await service.get_collaborations_network(department=department, faculty_id=fac_uuid)


@router.get("/opportunities")
async def opportunities(
    faculty_id: Optional[str] = Query(None, description="Filter by faculty ID"),
    db: AsyncSession = Depends(get_db),
):
    """Return verified funding grants and conference opportunities tailored to faculty research domains."""
    import uuid
    from app.services.research_intelligence_service import ResearchIntelligenceService

    fac_uuid = None
    if faculty_id:
        try:
            fac_uuid = uuid.UUID(faculty_id)
        except ValueError:
            pass

    service = ResearchIntelligenceService(db)
    return await service.get_research_opportunities(faculty_id=fac_uuid)


@router.get("/knowledge-graph")
async def knowledge_graph(
    faculty_id: Optional[str] = Query(None, description="Filter by faculty ID"),
    db: AsyncSession = Depends(get_db),
):
    """Return multi-entity institutional research knowledge graph."""
    import uuid
    from app.services.research_intelligence_service import ResearchIntelligenceService

    fac_uuid = None
    if faculty_id:
        try:
            fac_uuid = uuid.UUID(faculty_id)
        except ValueError:
            pass

    service = ResearchIntelligenceService(db)
    return await service.get_knowledge_graph(faculty_id=fac_uuid)


@router.get("/department-intelligence")
async def department_intelligence(
    department: Optional[str] = Query(None, description="Department name, e.g. CSE, EEE"),
    faculty_id: Optional[str] = Query(None, description="Optional faculty ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get deep departmental publication trends, faculty performance leaderboard,
    citations, research areas, and collaboration insights strictly from real DB records.
    """
    import uuid
    from app.services.research_intelligence_service import ResearchIntelligenceService

    fac_uuid = None
    if faculty_id:
        try:
            fac_uuid = uuid.UUID(faculty_id)
        except ValueError:
            pass
    elif current_user.faculty_id:
        fac_uuid = current_user.faculty_id

    # Resolve user's own department for RBAC isolation
    user_dept = None
    if current_user.faculty_id:
        fac = await db.get(FacultyProfile, current_user.faculty_id)
        if fac:
            user_dept = fac.department
    elif current_user.email:
        res = await db.execute(
            select(FacultyProfile).where(
                func.lower(FacultyProfile.institutional_email) == current_user.email.strip().lower()
            )
        )
        fac = res.scalars().first()
        if not fac:
            res = await db.execute(
                select(FacultyProfile).where(
                    func.lower(FacultyProfile.raw_email) == current_user.email.strip().lower()
                )
            )
            fac = res.scalars().first()
        if fac:
            user_dept = fac.department

    service = ResearchIntelligenceService(db)
    return await service.get_department_intelligence(
        department=department,
        faculty_id=fac_uuid,
        user_role=current_user.role,
        user_department=user_dept,
    )


@router.get("/department-comparisons")
async def department_comparisons(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get institutional cross-departmental comparative benchmarking matrix.
    """
    from app.services.research_intelligence_service import ResearchIntelligenceService

    service = ResearchIntelligenceService(db)
    return await service.get_department_comparisons()


