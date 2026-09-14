import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi import status
from httpx import AsyncClient

from app.main import app
from app.models.user import User
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor
from app.models.metrics import FacultyMetricSnapshot
from app.agents.reporting_agent import ReportingAgent
from app.api.v1.auth import get_current_user
from app.database import get_db


@pytest.mark.asyncio
async def test_reporting_agent_faculty_and_accreditation():
    mock_session = AsyncMock()
    fac_id = uuid.uuid4()
    
    mock_fac = FacultyProfile(
        id=fac_id,
        raw_name="Dr M Umadevi",
        first_name="M",
        last_name="Umadevi",
        department="CSE",
        designation="Associate Professor",
        institutional_email="druma_cse@vignan.ac.in",
    )
    
    mock_pub = Publication(
        id=uuid.uuid4(),
        title="Testing Report Publication Generation",
        year=2025,
        doi="10.1016/j.test.2025",
        journal_name="Journal of Research",
        verification_status="verified",
        metadata_confidence=95.0,
        citation_count=10,
        risk_level="none",
    )
    mock_author = PublicationAuthor(
        publication_id=mock_pub.id,
        faculty_id=fac_id,
        author_name_raw="Dr M Umadevi",
        faculty=mock_fac,
    )
    mock_pub.authors = [mock_author]
    mock_pub.sources = []

    mock_metrics = FacultyMetricSnapshot(
        faculty_id=fac_id,
        total_publications=1,
        total_citations=10,
        h_index=1,
        i10_index=1,
    )

    mock_session.get.return_value = mock_fac

    def mock_execute_side_effect(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "facultymetricsnapshot" in stmt_str:
            res.scalars.return_value.first.return_value = mock_metrics
        elif "faculty_profiles" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_fac]
            res.all.return_value = [("CSE", 1)]
        elif "publications" in stmt_str:
            res.scalars.return_value.unique.return_value.all.return_value = [mock_pub]
            res.scalars.return_value.all.return_value = [mock_pub]
        elif "count" in stmt_str:
            res.scalar.return_value = 1
        else:
            res.scalars.return_value.all.return_value = []
            res.all.return_value = []
            res.scalar.return_value = 0
        return res

    mock_session.execute.side_effect = mock_execute_side_effect

    agent = ReportingAgent(mock_session)
    
    # 1. Faculty report
    fac_rep = await agent.generate_faculty_report(fac_id)
    assert fac_rep["report_type"] == "FACULTY_REPORT"
    assert fac_rep["faculty"]["name"] == "M Umadevi"
    assert fac_rep["summary"]["total_publications"] == 1
    assert fac_rep["summary"]["verified_publications"] == 1
    
    # 2. Accreditation report
    acc_rep = await agent.generate_accreditation_evidence(standard="NAAC_NIRF", faculty_id=fac_id)
    assert acc_rep["report_type"] == "ACCREDITATION_EVIDENCE"
    assert len(acc_rep["records"]) == 1
    assert acc_rep["records"][0]["doi"] == "10.1016/j.test.2025"


@pytest.mark.asyncio
async def test_reports_api_endpoints():
    fac_id = uuid.uuid4()
    admin_user = User(
        id=uuid.uuid4(),
        email="admin@vignan.ac.in",
        full_name="Admin Reviewer",
        role="research_admin",
        is_active=True,
    )
    
    mock_fac = FacultyProfile(
        id=fac_id,
        raw_name="Dr M Umadevi",
        first_name="M",
        last_name="Umadevi",
        department="CSE",
        designation="Associate Professor",
        institutional_email="druma_cse@vignan.ac.in",
    )
    
    mock_pub = Publication(
        id=uuid.uuid4(),
        title="Accreditation Test Publication",
        year=2025,
        doi="10.1016/j.test.2025",
        journal_name="Journal of Research",
        verification_status="verified",
        metadata_confidence=95.0,
        citation_count=5,
        risk_level="none",
    )
    mock_pub.authors = [PublicationAuthor(publication_id=mock_pub.id, faculty_id=fac_id, faculty=mock_fac)]
    mock_pub.sources = []

    mock_db = AsyncMock()
    mock_db.get.return_value = mock_fac

    def mock_exec(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "faculty_profiles" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_fac]
            res.all.return_value = [("CSE", 1)]
        elif "publications" in stmt_str:
            res.scalars.return_value.unique.return_value.all.return_value = [mock_pub]
            res.scalars.return_value.all.return_value = [mock_pub]
        res.scalars.return_value.first.return_value = None
        res.scalar.return_value = 1
        return res

    mock_db.execute.side_effect = mock_exec

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: mock_db

    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Faculty report
        resp_f = await client.get(f"/api/v1/reports/faculty/{fac_id}")
        assert resp_f.status_code == 200
        assert resp_f.json()["report_type"] == "FACULTY_REPORT"

        # 2. Department report
        resp_d = await client.get("/api/v1/reports/department/CSE")
        assert resp_d.status_code == 200
        assert resp_d.json()["report_type"] == "DEPARTMENT_REPORT"

        # 3. Institution report
        resp_i = await client.get("/api/v1/reports/institution")
        assert resp_i.status_code == 200
        assert resp_i.json()["report_type"] == "INSTITUTION_REPORT"

        # 4. Accreditation report
        resp_a = await client.get("/api/v1/reports/accreditation?standard=NAAC_NIRF")
        assert resp_a.status_code == 200
        assert resp_a.json()["report_type"] == "ACCREDITATION_EVIDENCE"

        # 5. CSV Export
        resp_csv = await client.get("/api/v1/reports/export/csv?standard=NAAC_NIRF")
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers["content-type"]
        assert "Title of Paper" in resp_csv.text

    app.dependency_overrides.clear()
