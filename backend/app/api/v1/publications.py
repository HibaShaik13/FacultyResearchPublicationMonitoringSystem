"""
Publication endpoints — search, filter, evidence.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.publication import Publication, PublicationAuthor

router = APIRouter()


@router.get("/")
async def list_publications(
    year: Optional[int] = Query(None),
    department: Optional[str] = Query(None),
    verification_status: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search by title"),
    faculty_id: Optional[UUID] = Query(None, description="Filter by faculty ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List publications with filtering."""
    query = select(Publication).options(
        selectinload(Publication.authors),
        selectinload(Publication.sources),
    )

    if faculty_id:
        query = query.join(Publication.authors).where(PublicationAuthor.faculty_id == faculty_id)

    if year:
        query = query.where(Publication.year == year)
    if verification_status:
        query = query.where(Publication.verification_status == verification_status)
    if risk_level:
        query = query.where(Publication.risk_level == risk_level)
    if search:
        query = query.where(Publication.normalized_title.ilike(f"%{search.lower()}%"))

    query = query.order_by(Publication.year.desc().nullslast(), Publication.title).offset(skip).limit(limit)
    result = await db.execute(query)
    publications = result.scalars().unique().all()

    count_query = select(func.count(Publication.id))
    if faculty_id:
        count_query = count_query.join(Publication.authors).where(PublicationAuthor.faculty_id == faculty_id)
    if year:
        count_query = count_query.where(Publication.year == year)
    if verification_status:
        count_query = count_query.where(Publication.verification_status == verification_status)
    if risk_level:
        count_query = count_query.where(Publication.risk_level == risk_level)
    total = (await db.execute(count_query)).scalar()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": [
            {
                "id": str(p.id),
                "title": p.title,
                "doi": p.doi,
                "year": p.year,
                "journal_name": p.journal_name,
                "conference_name": p.conference_name,
                "publisher": p.publisher,
                "publication_type": p.publication_type,
                "verification_status": p.verification_status,
                "risk_level": p.risk_level,
                "citation_count": p.citation_count,
                "quartile": p.quartile,
                "indexing_status": p.indexing_status,
                "attribution_confidence": p.attribution_confidence,
                "authors": [
                    {
                        "name": a.author_name_raw,
                        "faculty_id": str(a.faculty_id) if a.faculty_id else None,
                        "confidence": a.attribution_confidence,
                    }
                    for a in p.authors
                ],
                "source_count": len(p.sources),
            }
            for p in publications
        ],
    }


@router.get("/stats")
async def publication_stats(db: AsyncSession = Depends(get_db)):
    """Get summary statistics for publications."""
    total = (await db.execute(select(func.count(Publication.id)))).scalar()
    verified = (
        await db.execute(
            select(func.count(Publication.id)).where(
                Publication.verification_status.in_(["auto_verified", "human_verified"])
            )
        )
    ).scalar()
    pending_review = (
        await db.execute(
            select(func.count(Publication.id)).where(
                Publication.verification_status == "review_required"
            )
        )
    ).scalar()
    with_doi = (
        await db.execute(
            select(func.count(Publication.id)).where(Publication.doi.isnot(None))
        )
    ).scalar()

    return {
        "total_publications": total,
        "verified": verified,
        "pending_review": pending_review,
        "pending": total - (verified or 0) - (pending_review or 0),
        "with_doi": with_doi,
    }


@router.get("/{publication_id}")
async def get_publication(publication_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single publication with full details and evidence."""
    query = (
        select(Publication)
        .options(
            selectinload(Publication.authors),
            selectinload(Publication.sources),
            selectinload(Publication.citation_snapshots),
        )
        .where(Publication.id == publication_id)
    )
    result = await db.execute(query)
    pub = result.scalar_one_or_none()

    if not pub:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Publication not found")

    return {
        "id": str(pub.id),
        "title": pub.title,
        "normalized_title": pub.normalized_title,
        "doi": pub.doi,
        "authors_raw": pub.authors_raw,
        "authors_parsed": pub.authors_parsed,
        "year": pub.year,
        "month": pub.month,
        "journal_name": pub.journal_name,
        "conference_name": pub.conference_name,
        "publisher": pub.publisher,
        "publication_type": pub.publication_type,
        "abstract": pub.abstract,
        "keywords": pub.keywords,
        "affiliation_text": pub.affiliation_text,
        "indexing_status": pub.indexing_status,
        "quartile": pub.quartile,
        "impact_factor": pub.impact_factor,
        "citescore": pub.citescore,
        "open_access": pub.open_access,
        "citation_count": pub.citation_count,
        "verification_status": pub.verification_status,
        "attribution_confidence": pub.attribution_confidence,
        "metadata_confidence": pub.metadata_confidence,
        "risk_level": pub.risk_level,
        "risk_reasons": pub.risk_reasons,
        "source_csv_text": pub.source_csv_text,
        "first_seen_at": pub.first_seen_at.isoformat() if pub.first_seen_at else None,
        "last_verified_at": pub.last_verified_at.isoformat() if pub.last_verified_at else None,
        "authors": [
            {
                "name": a.author_name_raw,
                "faculty_id": str(a.faculty_id) if a.faculty_id else None,
                "confidence": a.attribution_confidence,
                "method": a.attribution_method,
                "position": a.author_position,
            }
            for a in pub.authors
        ],
        "sources": [
            {
                "system": s.source_system,
                "source_id": s.source_id,
                "url": s.source_url,
                "discovered_at": s.discovered_at.isoformat() if s.discovered_at else None,
                "method": s.discovery_method,
            }
            for s in pub.sources
        ],
        "citation_history": [
            {
                "count": cs.citation_count,
                "source": cs.source,
                "date": cs.snapshot_date.isoformat(),
            }
            for cs in pub.citation_snapshots
        ],
    }
