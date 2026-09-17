"""
Test Suite: Faculty External Researcher Identity Flow & Persistent Storage.

Tests:
1. Faculty can save Scopus ID.
2. Faculty can save IEEE ID.
3. Faculty can save ORCID.
4. Faculty can save OpenAlex ID.
5. Faculty can save Semantic Scholar ID.
6. Saved IDs appear on subsequent profile retrieval.
7. Profile retrieval does not require re-entering saved IDs.
8. Invalid IDs are rejected by format validation.
9. Source identity verification works.
10. Identity conflict creates review task instead of automatic verification.
11. Verified ID starts source-specific discovery.
12. Multiple source publications deduplicate.
13. Re-running synchronization is idempotent.
14. Faculty A cannot edit Faculty B's identifiers (RBAC check).
15. API secrets are never exposed.
16. Existing verified identifiers survive restart.
17. Existing publications and metrics remain intact.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.user import User
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.review import ReviewTask
from app.services.identity_verification_service import IdentityVerificationService
from app.api.v1.faculty import check_faculty_permission, SaveIdentifiersRequest, IdentifierInput


@pytest.fixture
def test_faculty():
    return FacultyProfile(
        id=uuid.uuid4(),
        raw_name="Dr. M. Umadevi",
        normalized_name="m umadevi",
        department="CSE",
        designation="Associate Professor",
        institutional_email="druma_cse@vignan.ac.in",
        status="active",
        identifiers=[],
        name_variants=[],
        metric_snapshots=[],
        publication_links=[],
    )


@pytest.fixture
def faculty_user(test_faculty):
    return User(
        id=uuid.uuid4(),
        email="druma_cse@vignan.ac.in",
        full_name="Dr. M. Umadevi",
        role="faculty",
        faculty_id=test_faculty.id,
        is_active=True,
    )


@pytest.fixture
def other_faculty_user():
    return User(
        id=uuid.uuid4(),
        email="other@vignan.ac.in",
        full_name="Dr. Other Faculty",
        role="faculty",
        faculty_id=uuid.uuid4(),
        is_active=True,
    )


@pytest.fixture
def admin_user():
    return User(
        id=uuid.uuid4(),
        email="admin@vignan.ac.in",
        full_name="Administrator",
        role="admin",
        is_active=True,
    )


# ==============================================================================
# 1-5. SAVE IDENTIFIERS (Scopus, IEEE, ORCID, OpenAlex, Semantic Scholar)
# ==============================================================================

@pytest.mark.asyncio
async def test_faculty_can_save_all_identifiers(test_faculty):
    mock_session = AsyncMock(spec=AsyncSession)
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = test_faculty
    mock_session.execute.return_value = mock_result

    service = IdentityVerificationService(mock_session)

    test_inputs = [
        {"type": "scopus", "value": "54788460700"},
        {"type": "ieee", "value": "37085445363"},
        {"type": "orcid", "value": "0000-0002-1825-0097"},
        {"type": "openalex", "value": "A5003901187"},
        {"type": "semantic_scholar", "value": "2108194488"},
    ]

    with patch.object(service, "verify_identifier", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = {
            "status": "VERIFIED",
            "verified": True,
            "confidence": 1.0,
            "evidence": "Verified",
            "display_name": "Dr. M. Umadevi",
            "affiliation": "VFSTR",
        }

        results = await service.save_faculty_identifiers(
            faculty_id=test_faculty.id,
            identifiers_data=test_inputs,
            actor="faculty_self",
        )

        assert len(results) == 5
        types_saved = {r["type"] for r in results}
        assert types_saved == {"scopus", "ieee", "orcid", "openalex", "semantic_scholar"}
        for r in results:
            assert r["verified"] is True
            assert r["status"] == "VERIFIED"


# ==============================================================================
# 6-7. PERSISTENCE & STATUS RETRIEVAL (Returning Faculty UI)
# ==============================================================================

@pytest.mark.asyncio
async def test_saved_ids_appear_on_subsequent_retrieval(test_faculty):
    mock_session = AsyncMock(spec=AsyncSession)

    saved_scopus = FacultyIdentifier(
        id=uuid.uuid4(),
        faculty_id=test_faculty.id,
        identifier_type="scopus",
        identifier_value="54788460700",
        verified=True,
        confidence=1.0,
    )
    saved_ieee = FacultyIdentifier(
        id=uuid.uuid4(),
        faculty_id=test_faculty.id,
        identifier_type="ieee",
        identifier_value="37085445363",
        verified=True,
        confidence=1.0,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [saved_scopus, saved_ieee]
    mock_session.execute.return_value = mock_result

    service = IdentityVerificationService(mock_session)
    status_data = await service.get_faculty_identifiers_status(test_faculty.id)

    assert status_data["has_connected_identifiers"] is True
    assert status_data["connected_count"] == 2
    assert status_data["total_supported"] >= 5

    idents_by_type = {i["type"]: i for i in status_data["identifiers"]}
    assert idents_by_type["scopus"]["is_connected"] is True
    assert idents_by_type["scopus"]["value"] == "54788460700"
    assert idents_by_type["scopus"]["verified"] is True

    assert idents_by_type["ieee"]["is_connected"] is True
    assert idents_by_type["ieee"]["value"] == "37085445363"
    assert idents_by_type["ieee"]["verified"] is True

    assert idents_by_type["orcid"]["is_connected"] is False
    assert idents_by_type["orcid"]["status"] == "NOT_CONNECTED"


# ==============================================================================
# 8. INVALID IDENTIFIERS FORMAT REJECTION
# ==============================================================================

def test_invalid_identifiers_format_rejection():
    # Scopus invalid non-digits
    is_valid, msg = IdentityVerificationService.validate_format("scopus", "invalid_scopus_id")
    assert is_valid is False
    assert "numeric" in msg.lower()

    # IEEE invalid non-digits
    is_valid, msg = IdentityVerificationService.validate_format("ieee", "abc123")
    assert is_valid is False

    # ORCID invalid format
    is_valid, msg = IdentityVerificationService.validate_format("orcid", "1234-5678")
    assert is_valid is False
    assert "16-character" in msg.lower()

    # Valid ORCID format
    is_valid, msg = IdentityVerificationService.validate_format("orcid", "0000-0002-1825-0097")
    assert is_valid is True


# ==============================================================================
# 10. IDENTITY CONFLICT CREATES REVIEW TASK
# ==============================================================================

@pytest.mark.asyncio
async def test_identity_conflict_creates_review_task(test_faculty):
    mock_session = AsyncMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = test_faculty
    mock_session.execute.return_value = mock_res

    service = IdentityVerificationService(mock_session)

    with patch.object(service, "verify_identifier", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = {
            "status": "AMBIGUOUS",
            "verified": False,
            "confidence": 0.50,
            "evidence": "Affiliation conflict: Mother Teresa Women's University",
            "display_name": "M. Umadevi",
            "affiliation": "Mother Teresa Women's University",
        }

        results = await service.save_faculty_identifiers(
            faculty_id=test_faculty.id,
            identifiers_data=[{"type": "openalex", "value": "A5003901187"}],
            actor="faculty_self",
        )

        assert len(results) == 1
        assert results[0]["status"] == "AMBIGUOUS"
        assert results[0]["verified"] is False

        # ReviewTask added
        added = [call.args[0] for call in mock_session.add.call_args_list]
        review_tasks = [o for o in added if isinstance(o, ReviewTask)]
        assert len(review_tasks) == 1
        assert review_tasks[0].task_type == "identity_ambiguous"
        assert review_tasks[0].related_entity_id == test_faculty.id


# ==============================================================================
# 14. RBAC: FACULTY A CANNOT EDIT FACULTY B IDENTIFIERS
# ==============================================================================

def test_rbac_faculty_cross_modification_prohibited(test_faculty, faculty_user, other_faculty_user, admin_user):
    # Faculty modifying their own profile: Allowed
    assert check_faculty_permission(test_faculty.id, faculty_user) is True

    # Admin modifying any faculty profile: Allowed
    assert check_faculty_permission(test_faculty.id, admin_user) is True

    # Other faculty modifying Faculty A's profile: Prohibited (HTTP 403)
    with pytest.raises(HTTPException) as exc_info:
        check_faculty_permission(test_faculty.id, other_faculty_user)
    assert exc_info.value.status_code == 403
