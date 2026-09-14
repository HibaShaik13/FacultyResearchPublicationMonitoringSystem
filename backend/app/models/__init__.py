"""
Database models package.
Import all models here so Alembic can discover them.
"""

from app.models.user import User
from app.models.faculty import FacultyProfile, FacultyIdentifier, FacultyNameVariant
from app.models.affiliation import AffiliationVariant
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.metrics import CitationSnapshot, FacultyMetricSnapshot
from app.models.review import ReviewTask
from app.models.provenance import ProvenanceRecord, AuditLog
from app.models.agent import SyncRun, AgentRun
from app.models.notification import Notification, NotificationPreference

__all__ = [
    "User",
    "FacultyProfile",
    "FacultyIdentifier",
    "FacultyNameVariant",
    "AffiliationVariant",
    "Publication",
    "PublicationAuthor",
    "PublicationSource",
    "CitationSnapshot",
    "FacultyMetricSnapshot",
    "ReviewTask",
    "ProvenanceRecord",
    "AuditLog",
    "SyncRun",
    "AgentRun",
    "Notification",
    "NotificationPreference",
]
