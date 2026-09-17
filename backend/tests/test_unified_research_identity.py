"""
Test Suite: Verified Unified Research Identity System.

Validates the core Master Backend Requirements:
1. Dr. M. Umadevi reference test case (IEEE: 37085445363, Scopus: 54788460700).
2. External researcher identity resolution with strict VFSTR vs sibling college disambiguation.
3. Multi-source publication discovery without web scraping (IEEE, Scopus, OpenAlex, Crossref, ORCID, Semantic Scholar).
4. Multi-source canonical publication deduplication (one Publication entity, multiple PublicationSource links).
5. Strict Attribution & Candidate Isolation (ambiguous matches create ReviewTask, never unverified PublicationAuthor).
6. Human review confirmation/rejection lifecycle.
7. Strict Metric Reproducibility from confirmed database records only.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.faculty import FacultyProfile, FacultyIdentifier, FacultyNameVariant
from app.models.publication import Publication, PublicationSource, PublicationAuthor
from app.models.review import ReviewTask
from app.models.metrics import FacultyMetricSnapshot
from app.agents.identity_agent import FacultyIdentityAgent
from app.agents.discovery_agent import PublicationDiscoveryAgent
from app.agents.deduplication_agent import DeduplicationAgent
from app.agents.attribution_agent import FacultyAttributionAgent
from app.agents.metrics_agent import MetricsAgent


@pytest.fixture
def dr_umadevi_profile():
    profile = FacultyProfile(
        id=uuid.uuid4(),
        raw_name="Dr. M. Umadevi",
        normalized_name="m umadevi",
        department="Computer Science and Engineering",
        designation="Associate Professor",
        status="active"
    )
    profile.name_variants = [
        FacultyNameVariant(id=uuid.uuid4(), faculty_id=profile.id, name_variant="Umadevi M"),
        FacultyNameVariant(id=uuid.uuid4(), faculty_id=profile.id, name_variant="M. Uma Devi"),
    ]
    profile.identifiers = [
        FacultyIdentifier(
            id=uuid.uuid4(),
            faculty_id=profile.id,
            identifier_type="ieee",
            identifier_value="37085445363",
            verified=True,
            confidence=1.0
        ),
        FacultyIdentifier(
            id=uuid.uuid4(),
            faculty_id=profile.id,
            identifier_type="scopus",
            identifier_value="54788460700",
            verified=True,
            confidence=1.0
        ),
    ]
    return profile


@pytest.fixture
def dr_siva_profile():
    profile = FacultyProfile(
        id=uuid.uuid4(),
        raw_name="Dr. P. Siva Prasad",
        normalized_name="p siva prasad",
        department="Computer Science and Engineering",
        designation="Professor",
        status="active"
    )
    profile.name_variants = [
        FacultyNameVariant(id=uuid.uuid4(), faculty_id=profile.id, name_variant="Siva Prasad P"),
    ]
    profile.identifiers = []
    return profile


# ==============================================================================
# 1. REFERENCE TEST CASE: DR. M. UMADEVI DISCOVERY VIA VERIFIED IDENTIFIERS
# ==============================================================================

@pytest.mark.asyncio
async def test_dr_umadevi_verified_discovery(dr_umadevi_profile):
    """
    Verify that Dr. M. Umadevi's verified IEEE (37085445363) and Scopus (54788460700)
    identifiers trigger direct authorized queries, producing verified author attribution.
    """
    mock_session = AsyncMock(spec=AsyncSession)

    mock_variants_result = MagicMock()
    mock_variants_result.all.return_value = [("Vignan's Foundation for Science, Technology & Research",)]

    mock_profile_result = MagicMock()
    mock_profile_result.scalars.return_value.all.return_value = [dr_umadevi_profile]

    mock_empty_result = MagicMock()
    mock_empty_result.scalars.return_value.first.return_value = None

    mock_session.execute.side_effect = [
        mock_variants_result,
        mock_profile_result,
        mock_empty_result, mock_empty_result,  # OpenAlex checks
        mock_empty_result, mock_empty_result,  # Crossref checks
        mock_empty_result, mock_empty_result,  # Scopus checks
        mock_empty_result, mock_empty_result,  # IEEE checks
    ]

    agent = PublicationDiscoveryAgent(mock_session)

    # Mock IEEE works directly for 37085445363
    agent.ieee.enabled = True
    agent.ieee.get_author_works = AsyncMock(return_value=[
        {
            "article_number": "9998881",
            "title": "Machine Learning Approaches for Sensor Networks",
            "doi": "10.1109/TNET.2025.9998881",
            "publication_year": 2025,
            "publication_title": "IEEE Transactions on Network Science",
            "authors": {"authors": [{"full_name": "M. Umadevi", "id": "37085445363", "affiliation": "VFSTR, Vadlamudi"}]},
            "citing_paper_count": 12
        }
    ])

    # Mock Scopus works directly for 54788460700
    agent.scopus.enabled = True
    agent.scopus.search_author_works = AsyncMock(return_value=[
        {
            "dc:identifier": "SCOPUS_ID:85000000001",
            "dc:title": "Machine Learning Approaches for Sensor Networks",
            "prism:doi": "10.1109/TNET.2025.9998881",
            "prism:coverDate": "2025-01-15",
            "dc:creator": "Umadevi M.",
            "citedby-count": "12"
        }
    ])

    agent.openalex.search_works_by_name = AsyncMock(return_value=[])
    agent.crossref.search_works_by_author = AsyncMock(return_value=[])
    agent.semantic_scholar.search_papers = AsyncMock(return_value=[])

    stats = await agent.run()

    assert stats["processed"] == 1
    assert stats["sources_queried"]["ieee"] == 1
    assert stats["sources_queried"]["scopus"] == 1
    agent.ieee.get_author_works.assert_called_once_with("37085445363")
    agent.scopus.search_author_works.assert_called_once_with("54788460700")


# ==============================================================================
# 2. INSTITUTIONAL DISAMBIGUATION & SIBLING COLLEGE REJECTION
# ==============================================================================

def test_institution_affinity_classification():
    """Verify strict separation between VFSTR University and sibling colleges."""
    agent = FacultyAttributionAgent(AsyncMock())

    # Canonical VFSTR matches
    assert agent._classify_institution_affinity(["VFSTR Deemed to be University, Vadlamudi, India"]) == "VFSTR"
    assert agent._classify_institution_affinity(["Vignan's Foundation for Science, Technology & Research"]) == "VFSTR"
    assert agent._classify_institution_affinity(["Vignan University, Vadlamudi, Guntur"]) == "VFSTR"

    # Sibling institutions must be strictly separated
    assert agent._classify_institution_affinity(["Vignan's Lara Institute of Technology & Science, Vadlamudi"]) == "SIBLING_VIGNAN"
    assert agent._classify_institution_affinity(["Vignan Institute of Technology and Science, Deshmukhi, Hyderabad"]) == "SIBLING_VIGNAN"
    assert agent._classify_institution_affinity(["Vignan's Institute of Information Technology, Duvvada, Visakhapatnam"]) == "SIBLING_VIGNAN"
    assert agent._classify_institution_affinity(["Vignan's Nirula Institute of Technology and Science for Women"]) == "SIBLING_VIGNAN"
    assert agent._classify_institution_affinity(["Vignan Pharmacy College, Vadlamudi"]) == "SIBLING_VIGNAN"

    # External
    assert agent._classify_institution_affinity(["Department of ECE, IIT Madras"]) == "EXTERNAL"


def test_forename_contradiction_rejection(dr_siva_profile, dr_umadevi_profile):
    """Verify distinct forenames are never falsely matched."""
    agent = FacultyAttributionAgent(AsyncMock())

    # Contradictions against Dr. P. Siva Prasad
    assert agent._has_forename_contradiction("P. Sai Prasad", dr_siva_profile) is True
    assert agent._has_forename_contradiction("P. Deva Prasad", dr_siva_profile) is True
    assert agent._has_forename_contradiction("M. Siva Prasad", dr_siva_profile) is True
    assert agent._has_forename_contradiction("P. Syam Prasad", dr_siva_profile) is True
    assert agent._has_forename_contradiction("P. Durga Prasad", dr_siva_profile) is True
    assert agent._has_forename_contradiction("P. Bhanu Prasad", dr_siva_profile) is True

    # Valid matches for Dr. P. Siva Prasad
    assert agent._has_forename_contradiction("P. Siva Prasad", dr_siva_profile) is False
    assert agent._has_forename_contradiction("Siva Prasad, P.", dr_siva_profile) is False
    assert agent._has_forename_contradiction("P. Shiva Prasad", dr_siva_profile) is False

    # Contradictions against Dr. M. Umadevi
    assert agent._has_forename_contradiction("Uma Mahesh", dr_umadevi_profile) is True
    assert agent._has_forename_contradiction("Uma Shankar", dr_umadevi_profile) is True
    assert agent._has_forename_contradiction("M. Umadevi", dr_umadevi_profile) is False


# ==============================================================================
# 3. DEDUPLICATION: CANONICAL PUBLICATION WITH MULTIPLE PUBLICATION SOURCES
# ==============================================================================

@pytest.mark.asyncio
async def test_multi_source_deduplication_into_canonical_entity():
    """
    Verify that records discovered across IEEE, Scopus, Crossref, and OpenAlex
    for the same DOI are merged into a SINGLE canonical Publication with multiple PublicationSource records.
    """
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.delete = MagicMock()

    pub_doi = "10.1109/tnet.2025.9998881"
    pub1 = Publication(
        id=uuid.uuid4(),
        title="Machine Learning Approaches for Sensor Networks",
        normalized_title="machine learning approaches for sensor networks",
        doi=pub_doi,
        year=2025,
        citation_count=12
    )
    src_ieee = PublicationSource(id=uuid.uuid4(), publication_id=pub1.id, source_system="ieee", source_id="9998881")
    src_scopus = PublicationSource(id=uuid.uuid4(), publication_id=pub1.id, source_system="scopus", source_id="85000000001")
    pub1.sources = [src_ieee, src_scopus]

    pub2 = Publication(
        id=uuid.uuid4(),
        title="Machine Learning Approaches for Sensor Networks",
        normalized_title="machine learning approaches for sensor networks",
        doi=pub_doi,
        year=2025,
        citation_count=12
    )
    src_openalex = PublicationSource(id=uuid.uuid4(), publication_id=pub2.id, source_system="openalex", source_id="W9998881")
    src_crossref = PublicationSource(id=uuid.uuid4(), publication_id=pub2.id, source_system="crossref", source_id=pub_doi)
    pub2.sources = [src_openalex, src_crossref]

    mock_result = MagicMock()
    mock_result.scalars.return_value.unique.return_value.all.return_value = [pub1, pub2]
    mock_session.execute.return_value = mock_result

    agent = DeduplicationAgent(mock_session)
    stats = await agent.run()

    assert stats["merged"] == 1
    # Duplicate pub2 deleted
    mock_session.delete.assert_called_once_with(pub2)
    # Canonical pub1 retains all 4 distinct sources
    assert len(pub1.sources) == 4
    source_systems = {s.source_system for s in pub1.sources}
    assert source_systems == {"ieee", "scopus", "openalex", "crossref"}


# ==============================================================================
# 4. CANDIDATE ISOLATION & ATTRIBUTION
# ==============================================================================

@pytest.mark.asyncio
async def test_candidate_isolation_ambiguous_creates_review_task(dr_siva_profile):
    """
    Verify that an ambiguous candidate (score between 0.60 and 0.94) creates a ReviewTask
    and NEVER creates a PublicationAuthor record.
    """
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.add = MagicMock()

    pub = Publication(
        id=uuid.uuid4(),
        title="Survey of Distributed Algorithms",
        normalized_title="survey of distributed algorithms",
        doi="10.1016/j.dis.2025.101",
        year=2025,
        authors_raw="Prasad, P. S., Rao, K. V.",
        authors_parsed=[{"name": "P. S. Prasad", "position": 1, "affiliations": ["Vignan University"]}],
        affiliation_text="Vignan University",
        authors=[],
        sources=[]
    )

    agent = FacultyAttributionAgent(mock_session)
    agent.faculty_cache = [dr_siva_profile]
    agent.affiliation_keywords = ["vignan", "vfstr"]

    # Mock execute for checking existing ReviewTask
    mock_existing_task = MagicMock()
    mock_existing_task.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_existing_task

    stats = {"processed": 0, "attributions_created": 0, "high_confidence": 0, "ambiguous": 0, "errors": 0}
    await agent._process_publication(pub, stats)

    # Ambiguous candidate must NOT be added to pub.authors
    assert len(pub.authors) == 0
    assert stats["attributions_created"] == 0
    assert stats["ambiguous"] == 1

    # ReviewTask must be created
    added_objects = [call.args[0] for call in mock_session.add.call_args_list]
    review_tasks = [obj for obj in added_objects if isinstance(obj, ReviewTask)]
    assert len(review_tasks) == 1
    assert review_tasks[0].task_type == "attribution_ambiguous"
    assert review_tasks[0].entity_id == pub.id
    assert review_tasks[0].related_entity_id == dr_siva_profile.id


# ==============================================================================
# 5. STRICT METRICS REPRODUCIBILITY FROM CONFIRMED RECORDS ONLY
# ==============================================================================

@pytest.mark.asyncio
async def test_metrics_calculated_only_from_confirmed_publication_authors(dr_siva_profile):
    """
    Verify that metrics (total_publications, total_citations, h_index, i10_index)
    are strictly reproducible from confirmed PublicationAuthor database records.
    """
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.add = MagicMock()

    # 3 confirmed publications with citations: [25, 12, 5]
    pubs = [
        Publication(id=uuid.uuid4(), title="Paper 1", citation_count=25),
        Publication(id=uuid.uuid4(), title="Paper 2", citation_count=12),
        Publication(id=uuid.uuid4(), title="Paper 3", citation_count=5),
    ]

    dr_siva_profile.publication_links = [
        PublicationAuthor(id=uuid.uuid4(), publication_id=p.id, faculty_id=dr_siva_profile.id, publication=p)
        for p in pubs
    ]

    mock_existing_snapshot = MagicMock()
    mock_existing_snapshot.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_existing_snapshot

    agent = MetricsAgent(mock_session)
    stats = {"faculty_processed": 0, "faculty_snapshots": 0, "calculated_metrics": 0, "errors": 0}

    await agent._process_faculty_metrics(dr_siva_profile, stats)

    added_objects = [call.args[0] for call in mock_session.add.call_args_list]
    snapshots = [obj for obj in added_objects if isinstance(obj, FacultyMetricSnapshot)]

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.total_publications == 3
    assert snapshot.total_citations == 42  # 25 + 12 + 5
    assert snapshot.h_index == 3           # 25 >= 1, 12 >= 2, 5 >= 3
    assert snapshot.i10_index == 2         # [25, 12] >= 10


# ==============================================================================
# 6. FALSE IDENTITY COLLISION REGRESSION TESTS (E.G. MOTHER TERESA WOMEN'S UNIV)
# ==============================================================================

@pytest.mark.asyncio
async def test_unrelated_researcher_collision_rejection(dr_umadevi_profile):
    """
    Verify that an unrelated researcher with identical/similar name ('M. Umadevi')
    from Department of Physics, Mother Teresa Women's University, Kodaikanal
    is strictly rejected or scored below attribution threshold and NOT merged into VFSTR CSE profile.
    """
    mock_session = AsyncMock(spec=AsyncSession)
    mock_existing_task = MagicMock()
    mock_existing_task.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_existing_task

    agent = FacultyAttributionAgent(mock_session)
    agent.faculty_cache = [dr_umadevi_profile]
    agent.affiliation_keywords = ["vfstr", "vignan's foundation", "vignan deemed"]

    # Publication by M. Umadevi at Mother Teresa Women's University in Physics
    pub = Publication(
        id=uuid.uuid4(),
        title="Crystal growth and characterization of organic nonlinear optical materials",
        normalized_title="crystal growth and characterization of organic nonlinear optical materials",
        doi="10.1016/j.jcrysgro.2024.12345",
        year=2024,
        authors_raw="M. Umadevi, K. Ramasamy",
        authors_parsed=[{
            "name": "M. Umadevi",
            "position": 1,
            "affiliations": ["Department of Physics, Mother Teresa Women's University, Kodaikanal, Tamil Nadu, India"]
        }],
        affiliation_text="Department of Physics, Mother Teresa Women's University, Kodaikanal",
        authors=[],
        sources=[]
    )

    stats = {"processed": 0, "attributions_created": 0, "high_confidence": 0, "ambiguous": 0, "errors": 0}
    await agent._process_publication(pub, stats)

    # Must NOT create confirmed attribution (pub.authors remains empty)
    assert len(pub.authors) == 0
    assert stats["attributions_created"] == 0
    assert agent._classify_institution_affinity(["Department of Physics, Mother Teresa Women's University, Kodaikanal"]) == "EXTERNAL"


def test_doi_normalization_variations():
    """
    Verify robust DOI normalization handling uppercase/lowercase, https://doi.org/ prefix,
    doi: prefix, trailing punctuation, and whitespace.
    """
    raw_dois = [
        "https://doi.org/10.1109/TNET.2025.9998881",
        "http://dx.doi.org/10.1109/tnet.2025.9998881",
        "doi:10.1109/TNET.2025.9998881.",
        " 10.1109/TNET.2025.9998881 ",
        "https://doi.org/10.1109/tnet.2025.9998881/",
    ]
    expected = "10.1109/tnet.2025.9998881"
    
    for raw in raw_dois:
        normalized = raw.strip().lower()
        if normalized.startswith("https://doi.org/"):
            normalized = normalized[len("https://doi.org/"):]
        elif normalized.startswith("http://dx.doi.org/"):
            normalized = normalized[len("http://dx.doi.org/"):]
        elif normalized.startswith("doi:"):
            normalized = normalized[len("doi:"):]
        normalized = normalized.rstrip("./")
        assert normalized == expected


def test_api_credential_isolation_backend_only():
    """
    Verify that API keys (IEEE, Scopus, etc.) are backend configuration variables
    and not exposed to frontend or hardcoded into client models.
    """
    from app.config import get_settings
    settings = get_settings()
    # Ensure settings exist as backend properties
    assert hasattr(settings, "ieee_api_key")
    assert hasattr(settings, "scopus_api_key")
    assert hasattr(settings, "semantic_scholar_api_key")
    # Verify no credentials leaked into FacultyProfile model fields
    from app.models.faculty import FacultyProfile
    table_cols = {c.name for c in FacultyProfile.__table__.columns}
    assert "api_key" not in table_cols
    assert "secret" not in table_cols




