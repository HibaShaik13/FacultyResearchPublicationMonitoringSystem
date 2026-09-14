"""
Agent 11 — Human Review / Resolution Agent.
Manages the human-in-the-loop review queue, structures task evidence,
processes reviewer decisions (confirm/approve, reject, reassign, request_correction),
applies state transitions to publications and faculty, and generates immutable audit trails.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.faculty import FacultyProfile
from app.models.provenance import AuditLog, ProvenanceRecord
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.review import ReviewTask
from app.models.user import User

logger = logging.getLogger(__name__)


class HumanReviewAgent:
    """Agent 11 - Human Review / Resolution Agent"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(
        self,
        task_type: str,
        priority: str,
        entity_type: str,
        entity_id: uuid.UUID,
        explanation: str,
        evidence: Optional[Dict[str, Any]] = None,
        options: Optional[List[Dict[str, str]]] = None,
        related_entity_id: Optional[uuid.UUID] = None,
        agent_name: str = "System",
        sync_run_id: Optional[uuid.UUID] = None,
    ) -> ReviewTask:
        """
        Create a new review task if one for the same task_type and entity_id does not already exist pending.
        Idempotent creation.
        """
        # Check if identical pending task exists
        stmt = select(ReviewTask).where(
            ReviewTask.task_type == task_type,
            ReviewTask.entity_id == entity_id,
            ReviewTask.status == "pending",
        )
        existing = (await self.session.execute(stmt)).scalars().first()
        if existing:
            return existing

        default_options = options or [
            {"action": "CONFIRM", "label": "Confirm and verify this record"},
            {"action": "REJECT", "label": "Reject verification"},
            {"action": "REASSIGN", "label": "Reassign / Request metadata correction"},
            {"action": "DEFER", "label": "Defer for further investigation"},
        ]

        task = ReviewTask(
            task_type=task_type,
            priority=priority.lower(),
            status="pending",
            entity_type=entity_type,
            entity_id=entity_id,
            related_entity_id=related_entity_id,
            explanation=explanation,
            evidence=evidence or {},
            options=default_options,
            agent_name=agent_name,
            sync_run_id=sync_run_id,
        )
        self.session.add(task)
        await self.session.flush()
        return task

    async def resolve_task(
        self,
        task_id: uuid.UUID,
        decision: str,
        reviewer: User,
        comment: Optional[str] = None,
        corrected_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve a review task with a human reviewer decision.
        Updates publication/faculty state, records an immutable AuditLog, and registers ProvenanceRecord.
        """
        task = await self.session.get(ReviewTask, task_id)
        if not task:
            raise ValueError(f"ReviewTask with id {task_id} not found")

        decision_norm = decision.lower().strip()
        # Standardize decision names
        if decision_norm in ["confirm", "approve"]:
            canonical_decision = "approve"
        elif decision_norm in ["reject"]:
            canonical_decision = "reject"
        elif decision_norm in ["reassign", "correct", "request_correction"]:
            canonical_decision = "request_correction"
        elif decision_norm in ["defer"]:
            canonical_decision = "defer"
        else:
            canonical_decision = decision_norm

        old_task_status = task.status
        old_entity_status = None
        new_entity_status = None

        # Apply entity transitions
        if task.entity_type == "publication" and task.entity_id:
            pub = await self.session.get(Publication, task.entity_id)
            if pub:
                old_entity_status = pub.verification_status
                if canonical_decision == "approve":
                    new_entity_status = "human_verified"
                    pub.verification_status = "human_verified"
                    pub.metadata_confidence = max(pub.metadata_confidence or 0.0, 95.0)
                elif canonical_decision == "reject":
                    new_entity_status = "human_rejected"
                    pub.verification_status = "human_rejected"
                elif canonical_decision == "request_correction":
                    new_entity_status = "human_corrected"
                    pub.verification_status = "human_corrected"

                # Apply corrected fields if any
                if corrected_fields and isinstance(corrected_fields, dict):
                    for field, val in corrected_fields.items():
                        if hasattr(pub, field) and field not in ["id", "created_at"]:
                            setattr(pub, field, val)

                pub.last_verified_at = datetime.now(timezone.utc)

        elif task.entity_type == "faculty" and task.entity_id:
            fac = await self.session.get(FacultyProfile, task.entity_id)
            if fac:
                old_entity_status = fac.status
                if canonical_decision == "approve":
                    # If identifier match was confirmed
                    if task.task_type.lower() == "identifier_match" and task.evidence:
                        candidate = task.evidence.get("candidate", {})
                        if candidate.get("orcid") and not fac.institutional_email:
                            pass
                    new_entity_status = "verified"

        # Update ReviewTask record
        task.status = "resolved" if canonical_decision != "defer" else "deferred"
        task.decision = canonical_decision
        task.decision_detail = {
            "comment": comment or "",
            "corrected_fields": corrected_fields or {},
            "previous_entity_status": old_entity_status,
            "new_entity_status": new_entity_status,
            "reviewer_email": reviewer.email,
            "reviewer_name": reviewer.full_name,
        }
        task.decided_by = reviewer.id
        task.decided_at = datetime.now(timezone.utc)

        # Create immutable AuditLog entry
        audit = AuditLog(
            user_id=reviewer.id,
            action="review_decision",
            entity_type=task.entity_type,
            entity_id=task.entity_id,
            old_value={
                "task_id": str(task.id),
                "task_status": old_task_status,
                "entity_status": old_entity_status,
            },
            new_value={
                "task_id": str(task.id),
                "task_status": task.status,
                "decision": canonical_decision,
                "comment": comment,
                "entity_status": new_entity_status,
                "reviewer": reviewer.full_name,
            },
        )
        self.session.add(audit)

        # Create ProvenanceRecord entry
        prov = ProvenanceRecord(
            entity_type=task.entity_type or "publication",
            entity_id=task.entity_id or task.id,
            event_type="human_reviewed",
            source="human_reviewer",
            confidence=100.0,
            detail=f"Human reviewer {reviewer.full_name} ({reviewer.email}) submitted decision '{canonical_decision}'. Justification: {comment or 'None'}",
            agent_name="HumanReviewAgent",
        )
        self.session.add(prov)

        # Phase 15: Create Review Decision Notification
        try:
            from app.models.notification import Notification
            notif = Notification(
                title=f"Review Decision: {canonical_decision.replace('_', ' ').title()}",
                message=f"Task for {task.task_type.replace('_', ' ')} was decided by {reviewer.full_name}: {canonical_decision}.",
                notification_type="review_task_resolved",
                category="verification",
                severity="success" if canonical_decision in ["approve", "confirm"] else "warning",
                user_id=task.assigned_to,
                entity_type="review_task",
                entity_id=task.id,
                source_agent="HumanReviewAgent",
                source_event="review_decision_submitted",
                action_url="/verification",
                dedup_key=f"review_decided:{task.id}:{task.status}",
                is_read=False,
            )
            self.session.add(notif)
        except Exception:
            pass

        await self.session.commit()

        return {
            "status": "success",
            "task_id": str(task.id),
            "decision": canonical_decision,
            "new_entity_status": new_entity_status or task.status,
            "decided_at": task.decided_at.isoformat(),
            "reviewer": reviewer.full_name,
        }
