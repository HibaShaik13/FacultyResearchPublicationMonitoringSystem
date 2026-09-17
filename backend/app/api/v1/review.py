"""
Review queue endpoints for Human Review Agent (Phase 11).
Handles human verification, approvals, rejections, correction requests,
audit logging, and provenance tracking with role-based access control.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.auth import get_current_user
from app.database import get_db
from app.models.faculty import FacultyProfile
from app.models.provenance import AuditLog, ProvenanceRecord
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.review import ReviewTask
from app.models.user import User

from app.agents.human_review_agent import HumanReviewAgent

router = APIRouter()


class ReviewDecisionRequest(BaseModel):
    decision: str  # approve, reject, request_correction
    comment: Optional[str] = None
    corrected_fields: Optional[Dict[str, Any]] = None


@router.get("/stats")
async def review_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate statistics for the review queue."""
    # Base filter for RBAC
    user_faculty_id = current_user.faculty_id if current_user.role == "faculty" else None

    # If faculty user, get their publication IDs
    faculty_pub_ids = []
    if user_faculty_id:
        auth_stmt = select(PublicationAuthor.publication_id).where(
            PublicationAuthor.faculty_id == user_faculty_id
        )
        auth_res = await db.execute(auth_stmt)
        faculty_pub_ids = auth_res.scalars().all()

    async def get_count(status_filter: Optional[str] = None, priority_filter: Optional[str] = None, decision_filter: Optional[str] = None):
        stmt = select(func.count(ReviewTask.id))
        if status_filter:
            stmt = stmt.where(ReviewTask.status == status_filter)
        if priority_filter:
            stmt = stmt.where(ReviewTask.priority == priority_filter)
        if decision_filter:
            stmt = stmt.where(ReviewTask.decision == decision_filter)
            
        if user_faculty_id is not None:
            # Restrict strictly to tasks where this faculty is the target/candidate author or entity
            stmt = stmt.where(
                or_(
                    ReviewTask.related_entity_id == user_faculty_id,
                    ReviewTask.entity_id == user_faculty_id,
                )
            )
        res = await db.execute(stmt)
        return res.scalar() or 0

    pending = await get_count(status_filter="pending")
    high_priority = await get_count(status_filter="pending", priority_filter="high")
    critical_priority = await get_count(status_filter="pending", priority_filter="critical")
    resolved = await get_count(status_filter="resolved")
    approved = await get_count(decision_filter="approve")
    rejected = await get_count(decision_filter="reject")
    corrections = await get_count(decision_filter="request_correction")

    return {
        "pending": pending,
        "high_priority": high_priority + critical_priority,
        "resolved": resolved,
        "approved": approved,
        "rejected": rejected,
        "corrections": corrections,
        "user_role": current_user.role,
    }


@router.get("/queue")
async def review_queue(
    status_filter: str = Query("pending", alias="status"),
    priority: Optional[str] = None,
    task_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get review tasks with rich publication metadata, faculty authors, and evidence.
    Respects RBAC: research admins see all records, faculty see only their own actionable tasks.
    """
    user_faculty_id = current_user.faculty_id if current_user.role == "faculty" else None

    stmt = select(ReviewTask)

    # Filter status
    if status_filter != "all":
        stmt = stmt.where(ReviewTask.status == status_filter)

    # Filter priority
    if priority:
        stmt = stmt.where(ReviewTask.priority == priority)

    # Filter task type
    if task_type:
        stmt = stmt.where(ReviewTask.task_type == task_type)

    # Faculty data isolation: strictly own actionable tasks
    if user_faculty_id is not None:
        stmt = stmt.where(
            or_(
                ReviewTask.related_entity_id == user_faculty_id,
                ReviewTask.entity_id == user_faculty_id,
            )
        )

    stmt = stmt.order_by(
        desc(ReviewTask.priority == "critical"),
        desc(ReviewTask.priority == "high"),
        desc(ReviewTask.priority == "medium"),
        desc(ReviewTask.created_at),
    )

    result = await db.execute(stmt.offset(offset).limit(limit))
    tasks = result.scalars().all()

    # Total matching count
    count_stmt = select(func.count(ReviewTask.id))
    if status_filter != "all":
        count_stmt = count_stmt.where(ReviewTask.status == status_filter)
    if priority:
        count_stmt = count_stmt.where(ReviewTask.priority == priority)
    if task_type:
        count_stmt = count_stmt.where(ReviewTask.task_type == task_type)
    if user_faculty_id is not None:
        count_stmt = count_stmt.where(
            or_(
                ReviewTask.related_entity_id == user_faculty_id,
                ReviewTask.entity_id == user_faculty_id,
            )
        )
    total_count = (await db.execute(count_stmt)).scalar() or 0

    # Enrich each task with Publication and Faculty details
    enriched_tasks = []
    for task in tasks:
        task_data = {
            "id": str(task.id),
            "task_type": task.task_type,
            "priority": task.priority,
            "status": task.status,
            "entity_type": task.entity_type,
            "entity_id": str(task.entity_id) if task.entity_id else None,
            "explanation": task.explanation,
            "evidence": task.evidence or {},
            "options": task.options or {},
            "decision": task.decision,
            "decision_detail": task.decision_detail,
            "decided_by": str(task.decided_by) if task.decided_by else None,
            "decided_at": task.decided_at.isoformat() if task.decided_at else None,
            "agent_name": task.agent_name,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "publication": None,
            "faculty": None,
            "review_actions_allowed": (
                current_user.role in ["research_admin", "super_admin", "dept_admin"] or
                (
                    user_faculty_id is not None and (
                        task.related_entity_id == user_faculty_id or
                        task.entity_id == user_faculty_id
                    )
                )
            ),
        }

        # Check entity
        if task.entity_type == "publication" and task.entity_id:
            pub_stmt = (
                select(Publication)
                .options(
                    selectinload(Publication.authors).selectinload(PublicationAuthor.faculty),
                    selectinload(Publication.sources),
                )
                .where(Publication.id == task.entity_id)
            )
            pub_res = await db.execute(pub_stmt)
            pub = pub_res.scalars().first()
            if pub:
                authors_list = []
                for a in pub.authors:
                    fac_info = None
                    if a.faculty:
                        fac_info = {
                            "id": str(a.faculty.id),
                            "name": f"{a.faculty.first_name or ''} {a.faculty.last_name or ''}".strip() or a.faculty.raw_name,
                            "department": a.faculty.department,
                            "designation": a.faculty.designation,
                            "email": a.faculty.institutional_email or a.faculty.raw_email,
                        }
                    authors_list.append({
                        "name": a.author_name_raw,
                        "position": a.author_position,
                        "confidence": a.attribution_confidence,
                        "is_corresponding": a.is_corresponding,
                        "faculty": fac_info,
                    })

                sources_list = [
                    {
                        "source_system": s.source_system,
                        "source_id": s.source_id,
                        "discovered_at": s.discovered_at.isoformat() if s.discovered_at else None,
                    }
                    for s in pub.sources
                ]

                task_data["publication"] = {
                    "id": str(pub.id),
                    "title": pub.title,
                    "doi": pub.doi,
                    "year": pub.year,
                    "journal_name": pub.journal_name,
                    "conference_name": pub.conference_name,
                    "publisher": pub.publisher,
                    "publication_type": pub.publication_type,
                    "citation_count": pub.citation_count,
                    "risk_level": pub.risk_level,
                    "risk_reasons": pub.risk_reasons,
                    "verification_status": pub.verification_status,
                    "metadata_confidence": pub.metadata_confidence,
                    "attribution_confidence": pub.attribution_confidence,
                    "authors": authors_list,
                    "sources": sources_list,
                }

        elif task.entity_type == "faculty" and task.entity_id:
            fac = await db.get(FacultyProfile, task.entity_id)
            if fac:
                task_data["faculty"] = {
                    "id": str(fac.id),
                    "name": f"{fac.first_name or ''} {fac.last_name or ''}".strip() or fac.raw_name,
                    "department": fac.department,
                    "designation": fac.designation,
                    "email": fac.institutional_email or fac.raw_email,
                }

        # Filter by search term if provided
        if search:
            search_lower = search.lower()
            pub_title = task_data.get("publication", {}).get("title", "") if task_data.get("publication") else ""
            fac_name = task_data.get("faculty", {}).get("name", "") if task_data.get("faculty") else ""
            expl = task.explanation or ""
            if not (search_lower in pub_title.lower() or search_lower in fac_name.lower() or search_lower in expl.lower()):
                continue

        enriched_tasks.append(task_data)

    return {
        "data": enriched_tasks,
        "total": total_count,
        "offset": offset,
        "limit": limit,
    }


@router.post("/{task_id}/decide")
async def submit_decision(
    task_id: str,
    req: ReviewDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a human reviewer decision (approve, reject, request_correction).
    Updates publication status, records audit log, and registers provenance.
    """
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    task = await db.get(ReviewTask, task_uuid)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")

    # RBAC check: only admins or assigned staff or the linked faculty can decide
    is_admin = current_user.role in ["research_admin", "super_admin", "dept_admin"]
    is_authorized_faculty = False
    if current_user.role == "faculty" and current_user.faculty_id:
        if task.related_entity_id == current_user.faculty_id or task.entity_id == current_user.faculty_id:
            is_authorized_faculty = True

    if not is_admin and not is_authorized_faculty:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authorized research administrators or the linked faculty member can submit review decisions for this task",
        )

    # Delegate resolution to Agent 11 (HumanReviewAgent)
    agent = HumanReviewAgent(db)
    result = await agent.resolve_task(
        task_id=task_uuid,
        decision=req.decision,
        reviewer=current_user,
        comment=req.comment,
        corrected_fields=req.corrected_fields,
    )

    return result


@router.get("/history")
async def review_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get audit history of resolved review decisions with reviewer details.
    """
    user_faculty_id = current_user.faculty_id if current_user.role == "faculty" else None

    stmt = select(ReviewTask).where(ReviewTask.status == "resolved")

    if user_faculty_id is not None:
        stmt = stmt.where(
            or_(
                ReviewTask.entity_id == user_faculty_id,
                ReviewTask.related_entity_id == user_faculty_id,
            )
        )

    stmt = stmt.order_by(desc(ReviewTask.decided_at)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    history_items = []
    for t in tasks:
        reviewer_name = "Admin Reviewer"
        reviewer_email = ""
        if t.decided_by:
            rev_user = await db.get(User, t.decided_by)
            if rev_user:
                reviewer_name = rev_user.full_name
                reviewer_email = rev_user.email

        pub_title = None
        if t.entity_type == "publication" and t.entity_id:
            pub = await db.get(Publication, t.entity_id)
            if pub:
                pub_title = pub.title

        history_items.append({
            "id": str(t.id),
            "task_type": t.task_type,
            "entity_type": t.entity_type,
            "entity_id": str(t.entity_id) if t.entity_id else None,
            "entity_title": pub_title,
            "priority": t.priority,
            "decision": t.decision,
            "decision_detail": t.decision_detail or {},
            "reviewer_name": reviewer_name,
            "reviewer_email": reviewer_email,
            "decided_at": t.decided_at.isoformat() if t.decided_at else None,
            "explanation": t.explanation,
        })

    return {
        "data": history_items,
        "total": len(history_items),
    }
