"""
Tests for health check and system monitoring endpoints.
"""

import pytest
import httpx
from app.main import app
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_root_health_endpoint():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "app_name" in data
        assert "version" in data
        assert "institution" in data
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_api_health_endpoint():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_system_diagnostics_endpoint():
    token = create_access_token({"sub": "admin@vignan.ac.in", "role": "super_admin"})
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/health/system",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "system" in data
        assert "database" in data
        assert data["database"]["status"] == "operational"
        assert data["database"]["latency_ms"] >= 0
        assert "processing_metrics" in data
        assert "agents" in data
        assert len(data["agents"]) == 13
        assert "connectors" in data
        assert len(data["connectors"]) == 4


@pytest.mark.asyncio
async def test_system_audit_logs_endpoint():
    token = create_access_token({"sub": "admin@vignan.ac.in", "role": "super_admin"})
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/health/audit-logs",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total_returned" in data
