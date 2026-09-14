"""
Centralized Notification Service for Phase 15.
Handles event validation, duplicate prevention, RBAC & faculty isolation,
persistence, unread counts, and user preference management.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.faculty import FacultyProfile
from app.models.notification import Notification, NotificationPreference
from app.models.publication import Publication, PublicationAuthor
from app.models.review import ReviewTask
from app.models.user import User


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_notification(
        self,
        title: str,
        message: str,
        notification_type: str,
        severity: str = "info",
        category: str = "general",
        user_id: Optional[uuid.UUID] = None,
        faculty_id: Optional[uuid.UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        source_agent: Optional[str] = None,
        source_event: Optional[str] = None,
        action_url: Optional[str] = None,
        dedup_key: Optional[str] = None,
        event_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Notification]:
        """
        Creates and persists a real notification event with deduplication
        and preference filtering.
        """
        # Deduplication check
        if dedup_key:
            existing_stmt = select(Notification).where(Notification.dedup_key == dedup_key)
            existing = (await self.session.execute(existing_stmt)).scalars().first()
            if existing:
                return existing

        # User preference check if targeting a specific user
        if user_id:
            pref = await self.get_preferences(user_id)
            if category == "verification" and not pref.verification_alerts:
                return None
            elif category == "integrity" and not pref.integrity_alerts:
                return None
            elif category == "attribution" and not pref.attribution_alerts:
                return None
            elif category == "identity" and not pref.identity_alerts:
                return None
            elif category == "metrics" and not pref.metrics_updates:
                return None
            elif category == "pipeline" and not pref.pipeline_updates:
                return None
            elif category == "reports" and not pref.report_updates:
                return None

        notification = Notification(
            id=uuid.uuid4(),
            user_id=user_id,
            faculty_id=faculty_id,
            notification_type=notification_type,
            category=category,
            title=title,
            message=message,
            severity=severity,
            entity_type=entity_type,
            entity_id=entity_id,
            source_agent=source_agent,
            source_event=source_event,
            action_url=action_url,
            dedup_key=dedup_key,
            event_metadata=event_metadata or {},
            is_read=False,
            read_at=None,
        )

        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def get_notifications(
        self,
        current_user: User,
        filter_type: str = "all",
        is_read: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Notification], int]:
        """
        Retrieves paginated notifications for the authenticated user,
        strictly enforcing RBAC and faculty data isolation.
        """
        stmt = select(Notification)

        # Enforce faculty isolation vs Admin access
        if current_user.role == "faculty":
            user_fac_id = current_user.faculty_id
            if user_fac_id:
                stmt = stmt.where(
                    or_(
                        Notification.user_id == current_user.id,
                        Notification.faculty_id == user_fac_id,
                    )
                )
            else:
                stmt = stmt.where(Notification.user_id == current_user.id)
        else:
            # Admin users see institution-wide alerts (user_id is None and faculty_id is None)
            # as well as alerts assigned directly to them.
            stmt = stmt.where(
                or_(
                    Notification.user_id == current_user.id,
                    and_(Notification.user_id.is_(None), Notification.faculty_id.is_(None)),
                )
            )

        # Apply category filter
        filter_clean = filter_type.strip().lower()
        if filter_clean not in ["all", "unread"]:
            stmt = stmt.where(func.lower(Notification.category) == filter_clean)

        # Apply read state filter
        if filter_clean == "unread" or is_read is False:
            stmt = stmt.where(Notification.is_read.is_(False))
        elif is_read is True:
            stmt = stmt.where(Notification.is_read.is_(True))

        # Total count query
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = (await self.session.execute(count_stmt)).scalar() or 0

        # Paginate results
        stmt = stmt.order_by(desc(Notification.created_at)).offset(offset).limit(limit)
        results = (await self.session.execute(stmt)).scalars().all()

        return results, total_count

    async def get_unread_count(self, current_user: User) -> int:
        """
        Returns real count of unread notifications for current user.
        """
        stmt = select(func.count(Notification.id)).where(Notification.is_read.is_(False))

        if current_user.role == "faculty":
            user_fac_id = current_user.faculty_id
            if user_fac_id:
                stmt = stmt.where(
                    or_(
                        Notification.user_id == current_user.id,
                        Notification.faculty_id == user_fac_id,
                    )
                )
            else:
                stmt = stmt.where(Notification.user_id == current_user.id)
        else:
            stmt = stmt.where(
                or_(
                    Notification.user_id == current_user.id,
                    and_(Notification.user_id.is_(None), Notification.faculty_id.is_(None)),
                )
            )

        count = (await self.session.execute(stmt)).scalar() or 0
        return count

    async def mark_as_read(
        self, notification_id: uuid.UUID, current_user: User
    ) -> Optional[Notification]:
        """
        Marks an individual notification as read, ensuring the user is authorized.
        """
        stmt = select(Notification).where(Notification.id == notification_id)
        notification = (await self.session.execute(stmt)).scalars().first()
        if not notification:
            return None

        # Verify access permission
        if current_user.role == "faculty":
            if notification.user_id != current_user.id and notification.faculty_id != current_user.faculty_id:
                return None

        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def mark_all_as_read(self, current_user: User) -> int:
        """
        Marks all unread notifications for the user as read.
        """
        now = datetime.now(timezone.utc)
        stmt = update(Notification).where(Notification.is_read.is_(False))

        if current_user.role == "faculty":
            user_fac_id = current_user.faculty_id
            if user_fac_id:
                stmt = stmt.where(
                    or_(
                        Notification.user_id == current_user.id,
                        Notification.faculty_id == user_fac_id,
                    )
                )
            else:
                stmt = stmt.where(Notification.user_id == current_user.id)
        else:
            stmt = stmt.where(
                or_(
                    Notification.user_id == current_user.id,
                    and_(Notification.user_id.is_(None), Notification.faculty_id.is_(None)),
                )
            )

        stmt = stmt.values(is_read=True, read_at=now)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def get_preferences(self, user_id: uuid.UUID) -> NotificationPreference:
        """
        Retrieves user notification preferences, creating defaults if not existing.
        """
        stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        pref = (await self.session.execute(stmt)).scalars().first()
        if not pref:
            pref = NotificationPreference(
                id=uuid.uuid4(),
                user_id=user_id,
                verification_alerts=True,
                integrity_alerts=True,
                attribution_alerts=True,
                identity_alerts=True,
                metrics_updates=True,
                pipeline_updates=True,
                report_updates=True,
                email_notifications=False,
            )
            self.session.add(pref)
            await self.session.commit()
            await self.session.refresh(pref)
        return pref

    async def update_preferences(
        self, user_id: uuid.UUID, updates: Dict[str, Any]
    ) -> NotificationPreference:
        """
        Updates user notification preferences.
        """
        pref = await self.get_preferences(user_id)
        for field, value in updates.items():
            if hasattr(pref, field) and isinstance(value, bool):
                setattr(pref, field, value)

        await self.session.commit()
        await self.session.refresh(pref)
        return pref

    async def sync_existing_database_events(self) -> int:
        """
        Synchronizes existing real database events (pending review tasks, integrity flags,
        and sync runs) into notifications deterministically without creating duplicates.
        """
        created_count = 0

        # 1. Pending Review Tasks -> Notifications for affected faculty / admin
        review_stmt = (
            select(ReviewTask)
            .where(ReviewTask.status == "pending")
            .limit(50)
        )
        tasks = (await self.session.execute(review_stmt)).scalars().all()

        for task in tasks:
            dedup = f"review_task:{task.id}"
            title = f"Human Review Required: {task.task_type.replace('_', ' ').title()}"
            msg = task.explanation or f"Task {task.task_type} requires manual verification."
            severity = "critical" if task.priority in ["critical", "high"] else "warning"

            # Determine category
            category = "verification"
            if "attribution" in task.task_type:
                category = "attribution"
            elif "identifier" in task.task_type or "identity" in task.task_type:
                category = "identity"
            elif "risk" in task.task_type or "integrity" in task.task_type:
                category = "integrity"

            # Find faculty_id if entity is a publication or faculty
            target_faculty_id = None
            if task.entity_type == "faculty":
                target_faculty_id = task.entity_id
            elif task.entity_type == "publication" and task.entity_id:
                # Find corresponding faculty author
                auth_stmt = select(PublicationAuthor.faculty_id).where(
                    PublicationAuthor.publication_id == task.entity_id
                ).limit(1)
                target_faculty_id = (await self.session.execute(auth_stmt)).scalar()

            created = await self.create_notification(
                title=title,
                message=msg,
                notification_type=f"review_{task.task_type}",
                severity=severity,
                category=category,
                faculty_id=target_faculty_id,
                entity_type="review_task",
                entity_id=task.id,
                source_agent=task.agent_name or "HumanReviewAgent",
                source_event="review_task_created",
                action_url="/verification",
                dedup_key=dedup,
                event_metadata={"priority": task.priority, "task_type": task.task_type},
            )
            if created:
                created_count += 1

        return created_count
