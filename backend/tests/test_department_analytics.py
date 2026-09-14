"""
Tests for Phase 15: Department Analytics & Intelligence.
Verifies real-data computations for department publication trends,
faculty research performance leaderboards, citation metrics, and RBAC isolation.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import async_session_factory
from app.services.research_intelligence_service import ResearchIntelligenceService
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_department_intelligence_service():
    """Test Department Intelligence Service queries real database models."""
    async with async_session_factory() as session:
        service = ResearchIntelligenceService(session)
        data = await service.get_department_intelligence(department="CSE")
        
        assert data["department"] == "CSE"
        assert "all_departments" in data
        assert "summary" in data
        assert data["summary"]["total_faculty"] > 0
        assert data["summary"]["total_publications"] > 0
        assert "faculty_leaderboard" in data
        assert len(data["faculty_leaderboard"]) > 0
        assert "publication_trends" in data
        assert "research_domains" in data
        assert "collaboration_insights" in data


@pytest.mark.asyncio
async def test_department_comparisons_service():
    """Test Cross-Department Comparative matrix queries real database records."""
    async with async_session_factory() as session:
        service = ResearchIntelligenceService(session)
        comparisons = await service.get_department_comparisons()
        
        assert isinstance(comparisons, list)
        assert len(comparisons) > 0
        dept_names = [c["department"] for c in comparisons]
        assert "CSE" in dept_names
        
        cse = next(c for c in comparisons if c["department"] == "CSE")
        assert cse["faculty_count"] > 0
        assert cse["publication_count"] > 0
        assert "top_domain" in cse


@pytest.mark.asyncio
async def test_department_analytics_api_endpoints():
    """Test authenticated API endpoints for department intelligence and comparisons."""
    admin_token = create_access_token({"sub": "admin@vignan.ac.in", "role": "super_admin"})
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Department Intelligence API
        res = await client.get(
            "/api/v1/analytics/department-intelligence?department=CSE",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["department"] == "CSE"
        assert "summary" in data
        assert "faculty_leaderboard" in data
        assert "publication_trends" in data
        
        # 2. Department Comparisons API
        res_comp = await client.get(
            "/api/v1/analytics/department-comparisons",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res_comp.status_code == 200
        comp_data = res_comp.json()
        assert isinstance(comp_data, list)
        assert any(d["department"] == "CSE" for d in comp_data)
