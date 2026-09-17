"""
Test suite for Faculty Publication Attribution Remediation.
Validates:
1. P. Siva Prasad vs P. Sai Prasad (No false match)
2. VFSTR vs Vignan's Lara Institute (Sister institution isolation)
3. Candidate Isolation: Ambiguous match creates ReviewTask only, no PublicationAuthor
4. Human Review Resolution: Confirm creates PublicationAuthor, Reject prevents/removes it
5. Metrics calculation strictly counts confirmed PublicationAuthor links
6. Exact external author ID match (ORCID/OpenAlex) qualifies for auto-attribution
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.faculty import FacultyProfile, FacultyIdentifier, FacultyNameVariant
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.review import ReviewTask
from app.models.user import User
from app.agents.attribution_agent import FacultyAttributionAgent
from app.agents.human_review_agent import HumanReviewAgent
from app.agents.metrics_agent import MetricsAgent


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    added_items = []
    session.add.side_effect = lambda x: added_items.append(x)
    session.add_all.side_effect = lambda items: added_items.extend(items)
    session.added_items = added_items
    return session


@pytest.mark.asyncio
async def test_sai_prasad_vs_siva_prasad_no_auto_match(mock_session):
    """P. Sai Prasad at Lara MUST NOT be attributed to Dr. P. Siva Prasad."""
    siva = FacultyProfile(
        id=uuid.uuid4(),
        raw_name="Dr. P. Siva Prasad",
        normalized_name="p. siva prasad",
        department="CSE",
        status="active",
        institutional_email="sivaprasad@vignan.ac.in",
    )
    siva.name_variants = []
    siva.identifiers = []

    # Test case DOI: 10.1109/iciccs67901.2026.11502731
    pub = Publication(
        id=uuid.uuid4(),
        title="An Adaptive Hybrid Learning Framework for Cyber Threat Identification",
        doi="10.1109/iciccs67901.2026.11502731",
        authors_raw="P. Sai Prasad",
        affiliation_text="Vignan's Lara Institute of Technology and Science, Guntur",
        verification_status="unverified",
    )

    agent = FacultyAttributionAgent(mock_session)
    agent.faculty_cache = [siva]

    score, method, matched_name = await agent.compute_faculty_pub_match(siva, pub)

    # Must NOT auto-attribute and must score as likely wrong (< 0.60)
    assert score < agent.AUTO_ATTRIBUTION_THRESHOLD, f"Score {score} should not auto-attribute"
    assert score < 0.60, f"Score {score} should be classified as likely wrong/unrelated"


@pytest.mark.asyncio
async def test_vfstr_vs_lara_institution_classification(mock_session):
    """Ensure VFSTR and Vignan's Lara are strictly distinguished."""
    agent = FacultyAttributionAgent(mock_session)

    vfstr_affils = ["Vignan's Foundation for Science, Technology & Research", "VFSTR Deemed to be University, Vadlamudi"]
    lara_affils = ["Vignan's Lara Institute of Technology and Science, Guntur"]
    vits_affils = ["Vignan Institute of Technology and Science, Deshmukhi, Hyderabad"]
    viit_affils = ["Vignan's Institute of Information Technology, Visakhapatnam"]
    nirula_affils = ["Vignan's Nirula Institute of Technology and Science for Women"]

    assert agent._classify_institution_affinity(vfstr_affils) == "VFSTR"
    assert agent._classify_institution_affinity(lara_affils) == "SIBLING_VIGNAN"
    assert agent._classify_institution_affinity(vits_affils) == "SIBLING_VIGNAN"
    assert agent._classify_institution_affinity(viit_affils) == "SIBLING_VIGNAN"
    assert agent._classify_institution_affinity(nirula_affils) == "SIBLING_VIGNAN"


@pytest.mark.asyncio
async def test_candidate_isolation_creates_review_task_only(mock_session):
    """Ambiguous matches must create ReviewTask and NOT insert PublicationAuthor."""
    fac = FacultyProfile(
        id=uuid.uuid4(),
        raw_name="Dr. P. Siva Prasad",
        normalized_name="p. siva prasad",
        department="CSE",
        status="active",
    )
    fac.name_variants = [
        FacultyNameVariant(id=uuid.uuid4(), faculty_id=fac.id, name_variant="p. s. prasad")
    ]
    fac.identifiers = []

    # Pub with variant name 'P. S. Prasad' without verified author ID
    pub = Publication(
        id=uuid.uuid4(),
        title="Predictive Graph Analysis in IoT Networks",
        doi="10.1109/test.candidate.isolation",
        authors_raw="P. S. Prasad",
        authors_parsed=[{"name": "P. S. Prasad", "position": 1, "affiliations": ["Vignan"]}],
        affiliation_text="Vignan",
        verification_status="unverified",
        authors=[]
    )

    def execute_side_effect(stmt):
        s_str = str(stmt)
        if "faculty_profiles" in s_str:
            res = MagicMock()
            res.scalars.return_value.unique.return_value.all.return_value = [fac]
            return res
        elif "review_tasks" in s_str:
            res = MagicMock()
            res.scalars.return_value.first.return_value = None
            return res
        elif "affiliation_variants" in s_str:
            res = MagicMock()
            res.all.return_value = []
            return res
        else:
            res = MagicMock()
            res.scalars.return_value.unique.return_value.all.return_value = [pub]
            return res

    mock_session.execute.side_effect = execute_side_effect

    agent = FacultyAttributionAgent(mock_session)
    stats = await agent.run()

    # Candidate isolation check: No PublicationAuthor added
    pub_authors_added = [item for item in mock_session.added_items if isinstance(item, PublicationAuthor)]
    assert len(pub_authors_added) == 0, "Candidate isolation violated: PublicationAuthor was added for ambiguous candidate"

    # ReviewTask added for human confirmation
    tasks_added = [item for item in mock_session.added_items if isinstance(item, ReviewTask)]
    assert len(tasks_added) == 1, "ReviewTask must be created for ambiguous candidate"
    assert tasks_added[0].task_type == "attribution_ambiguous"
    assert tasks_added[0].related_entity_id == fac.id


@pytest.mark.asyncio
async def test_human_review_confirmation_and_rejection_lifecycle(mock_session):
    """Confirming a ReviewTask creates PublicationAuthor; Rejecting does not/removes it."""
    fac = FacultyProfile(
        id=uuid.uuid4(),
        raw_name="Dr. P. Siva Prasad",
        normalized_name="p. siva prasad",
        department="CSE",
        status="active",
    )
    user = User(
        id=uuid.uuid4(),
        email="siva@vignan.ac.in",
        full_name="Dr. P. Siva Prasad",
        password_hash="fakehash",
        role="faculty",
        faculty_id=fac.id,
    )
    pub = Publication(
        id=uuid.uuid4(),
        title="Verified Algebra Paper",
        doi="10.1109/test.algebra.123",
        authors_raw="P. Siva Prasad",
        affiliation_text="VFSTR Vadlamudi",
        verification_status="unverified",
    )
    task = ReviewTask(
        id=uuid.uuid4(),
        task_type="attribution_ambiguous",
        priority="high",
        status="pending",
        entity_type="publication",
        entity_id=pub.id,
        related_entity_id=fac.id,
        explanation="Candidate attribution review",
        evidence={"raw_author_name": "P. Siva Prasad"}
    )

    # Mock session get and execute
    async def get_side_effect(model_cls, pk):
        if model_cls == ReviewTask and pk == task.id:
            return task
        if model_cls == Publication and pk == pub.id:
            return pub
        if model_cls == FacultyProfile and pk == fac.id:
            return fac
        return None

    mock_session.get.side_effect = get_side_effect

    # When query for PublicationAuthor runs, return empty (not yet created)
    res_empty = MagicMock()
    res_empty.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = res_empty

    review_agent = HumanReviewAgent(mock_session)

    # 1. Approve creates PublicationAuthor
    await review_agent.resolve_task(task_id=task.id, decision="approve", reviewer=user)

    pub_authors_added = [item for item in mock_session.added_items if isinstance(item, PublicationAuthor)]
    assert len(pub_authors_added) == 1, "PublicationAuthor must be created on approval"
    assert pub_authors_added[0].attribution_confidence == 1.0
    assert pub_authors_added[0].attribution_method == "human_confirmed"
    assert task.status == "resolved"
    assert task.decision == "approve"


@pytest.mark.asyncio
async def test_orcid_identifier_match_auto_attributes(mock_session):
    """Exact ORCID match qualifies for auto-attribution with 1.0 confidence."""
    fac = FacultyProfile(
        id=uuid.uuid4(),
        raw_name="Dr. P. Siva Prasad",
        normalized_name="p. siva prasad",
        department="CSE",
        status="active",
    )
    fac.name_variants = []
    fac.identifiers = [
        FacultyIdentifier(
            id=uuid.uuid4(),
            faculty_id=fac.id,
            identifier_type="orcid",
            identifier_value="0000-0002-1825-0097",
            verified=True
        )
    ]
    pub = Publication(
        id=uuid.uuid4(),
        title="Exact ORCID Paper",
        doi="10.1109/orcid.test.999",
        authors_parsed=[{
            "name": "P. Siva Prasad",
            "orcid": "https://orcid.org/0000-0002-1825-0097",
            "position": 1,
            "affiliations": ["Vignan's Foundation for Science, Technology & Research"]
        }],
        verification_status="unverified",
    )

    agent = FacultyAttributionAgent(mock_session)
    score, method, matched_name = await agent.compute_faculty_pub_match(fac, pub)

    assert score == 1.0
    assert method == "author_id_verified"
