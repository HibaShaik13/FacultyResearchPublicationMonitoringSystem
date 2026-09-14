import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.faculty import FacultyProfile
from app.models.publication import Publication
from app.models.agent import SyncRun, AgentRun
from app.orchestrator.pipeline_orchestrator import PipelineOrchestrator

@pytest.mark.asyncio
async def test_pipeline_orchestrator_status():
    """Test retrieving live status and metrics for all 13 agents."""
    mock_session = AsyncMock(spec=AsyncSession)

    def execute_side_effect(stmt):
        str_stmt = str(stmt).lower()
        mock_res = MagicMock()
        if "count(faculty_profiles.id)" in str_stmt:
            mock_res.scalar.return_value = 24
        elif "count(publications.id)" in str_stmt and "verification_status" in str_stmt:
            mock_res.scalar.return_value = 199
        elif "count(publications.id)" in str_stmt:
            mock_res.scalar.return_value = 210
        elif "count(review_tasks.id)" in str_stmt:
            mock_res.scalar.return_value = 5
        elif "sum(publications.citation_count)" in str_stmt:
            mock_res.scalar.return_value = 542
        elif "sync_runs" in str_stmt:
            mock_res.scalars.return_value.first.return_value = None
        else:
            mock_res.scalar.return_value = 0
            mock_res.scalars.return_value.all.return_value = []
        return mock_res

    mock_session.execute.side_effect = execute_side_effect

    orchestrator = PipelineOrchestrator(mock_session)
    status_data = await orchestrator.get_pipeline_status()

    # Check 13 agents catalog
    assert len(status_data["agents"]) == 13
    assert status_data["agents"][0]["name"] == "Faculty Identity Agent"
    assert status_data["agents"][12]["name"] == "Pipeline Orchestrator Agent"

    # Check system health rollup
    health = status_data["system_health"]
    assert health["faculty_count"] == 24
    assert health["publications_count"] == 210
    assert health["verified_count"] == 199
    assert health["total_citations"] == 542
    assert "verification_integrity_rate" in health

@pytest.mark.asyncio
async def test_pipeline_orchestrator_execution_flow():
    """Test running full pipeline synchronization cycle."""
    mock_session = AsyncMock(spec=AsyncSession)
    user_id = uuid.uuid4()

    orchestrator = PipelineOrchestrator(mock_session)

    # Patch the sub-agent run methods to verify orchestration flow
    with patch("app.orchestrator.pipeline_orchestrator.FacultyIdentityAgent.run", new_callable=AsyncMock) as m_ident, \
         patch("app.orchestrator.pipeline_orchestrator.PublicationDiscoveryAgent.run", new_callable=AsyncMock) as m_disc, \
         patch("app.orchestrator.pipeline_orchestrator.MetadataNormalizationAgent.run", new_callable=AsyncMock) as m_norm, \
         patch("app.orchestrator.pipeline_orchestrator.DeduplicationAgent.run", new_callable=AsyncMock) as m_dedup, \
         patch("app.orchestrator.pipeline_orchestrator.FacultyAttributionAgent.run", new_callable=AsyncMock) as m_attr, \
         patch("app.orchestrator.pipeline_orchestrator.ResearchMetadataEnrichmentAgent.run", new_callable=AsyncMock) as m_enrich, \
         patch("app.orchestrator.pipeline_orchestrator.ResearchIntegrityAgent.run", new_callable=AsyncMock) as m_integ, \
         patch("app.orchestrator.pipeline_orchestrator.MetricsAgent.run", new_callable=AsyncMock) as m_met, \
         patch("app.orchestrator.pipeline_orchestrator.VerificationAgent.run", new_callable=AsyncMock) as m_verif, \
         patch("app.orchestrator.pipeline_orchestrator.ReportingAgent.generate_institution_report", new_callable=AsyncMock) as m_rep:

        m_ident.return_value = {"processed": 24, "resolved": 24, "errors": 0}
        m_disc.return_value = {"discovered": 15, "errors": 0}
        m_norm.return_value = {"normalized": 15, "errors": 0}
        m_dedup.return_value = {"merged": 2, "errors": 0}
        m_attr.return_value = {"attributed": 13, "errors": 0}
        m_enrich.return_value = {"enriched": 13, "errors": 0}
        m_integ.return_value = {"audited": 13, "errors": 0}
        m_met.return_value = {"calculated_metrics": 13, "errors": 0}
        m_verif.return_value = {"verified": 12, "needs_review": 1, "errors": 0}
        m_rep.return_value = {"total_publications": 200, "total_citations": 500, "overall_verification_rate": 95.0}

        result = await orchestrator.run_full_pipeline(triggered_by=user_id, trigger="test_suite")

        assert result["sync_run_status"] == "completed"
        assert result["total_errors"] == 0
        assert "Faculty Identity Resolution" in result["stages"]
        assert "Publication Discovery" in result["stages"]
        assert "Reporting & Accreditation Rollup" in result["stages"]

        # Verify all agent stages were invoked
        assert m_ident.called
        assert m_disc.called
        assert m_norm.called
        assert m_dedup.called
        assert m_attr.called
        assert m_enrich.called
        assert m_integ.called
        assert m_met.called
        assert m_verif.called
        assert m_rep.called
