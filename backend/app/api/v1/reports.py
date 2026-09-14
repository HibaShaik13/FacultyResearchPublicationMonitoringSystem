"""
Report generation endpoints for Agent 12 (Reporting & Accreditation Agent).
Provides structured JSON reports and CSV export data for NAAC, NIRF, NBA,
and institutional research administration.
"""

import csv
import io
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.reporting_agent import ReportingAgent
from app.api.v1.auth import get_current_user
from app.database import get_db
from app.models.user import User

router = APIRouter()


@router.get("/faculty/{faculty_id}")
async def faculty_report(
    faculty_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate individual faculty publication and metrics report."""
    try:
        fac_uuid = uuid.UUID(faculty_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid faculty ID format")

    # RBAC: faculty can only view their own report
    if current_user.role == "faculty" and current_user.faculty_id != fac_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faculty members may only access their own research report",
        )

    agent = ReportingAgent(db)
    try:
        report = await agent.generate_faculty_report(fac_uuid)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/department/{department}")
async def department_report(
    department: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate department research summary and faculty output ranking."""
    agent = ReportingAgent(db)
    return await agent.generate_department_report(department)


@router.get("/institution")
async def institution_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate university-wide research performance and accreditation metrics."""
    agent = ReportingAgent(db)
    return await agent.generate_institution_report()


@router.get("/accreditation")
async def accreditation_evidence(
    standard: str = Query("NAAC_NIRF", description="Accreditation Standard (NAAC, NIRF, NBA)"),
    department: Optional[str] = Query(None, description="Filter by department"),
    faculty_id: Optional[str] = Query(None, description="Filter by faculty ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate accreditation evidence table (e.g. NAAC 3.4.4 / NIRF Research Output).
    Respects RBAC: faculty users see their own verified publications.
    """
    fac_uuid = None
    if current_user.role == "faculty" and current_user.faculty_id:
        fac_uuid = current_user.faculty_id
    elif faculty_id:
        try:
            fac_uuid = uuid.UUID(faculty_id)
        except ValueError:
            pass

    agent = ReportingAgent(db)
    return await agent.generate_accreditation_evidence(
        standard=standard,
        department=department,
        faculty_id=fac_uuid,
    )


@router.get("/export/csv")
async def export_accreditation_csv(
    standard: str = Query("NAAC_NIRF"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export accreditation evidence as a downloadable CSV file."""
    fac_uuid = current_user.faculty_id if current_user.role == "faculty" else None

    agent = ReportingAgent(db)
    data = await agent.generate_accreditation_evidence(
        standard=standard,
        faculty_id=fac_uuid,
    )

    records = data.get("records", [])

    output = io.StringIO()
    writer = csv.writer(output)

    # Write Header
    writer.writerow([
        "Sl. No",
        "Title of Paper",
        "Name of the Author(s)",
        "Department",
        "Journal / Conference Name",
        "Year of Publication",
        "ISSN / ISBN",
        "DOI",
        "Indexing (SCIE / Scopus / UGC)",
        "Verification Status",
        "Confidence Score",
        "Affiliation Verified",
    ])

    for r in records:
        writer.writerow([
            r.get("sl_no"),
            r.get("title"),
            r.get("all_authors"),
            r.get("department"),
            r.get("journal_or_conference"),
            r.get("year"),
            r.get("issn_isbn"),
            r.get("doi"),
            r.get("indexing"),
            r.get("verification_status"),
            r.get("confidence_score"),
            "YES" if r.get("institutional_affiliation_verified") else "NO",
        ])

    csv_content = output.getvalue()
    filename = f"VFSTR_Accreditation_Report_{datetime.now().strftime('%Y%m%d')}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
