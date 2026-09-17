"""
Attribution Reconciliation Script
Performs safe backup, re-evaluates all PublicationAuthor relationships using
the remediated FacultyAttributionAgent logic, detaches false positives / candidates,
ensures candidate ReviewTasks exist for ambiguous matches, and recalculates metrics.
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.review import ReviewTask
from app.agents.attribution_agent import FacultyAttributionAgent
from app.agents.metrics_agent import MetricsAgent


BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backups"))


async def backup_publication_authors(session: AsyncSession) -> str:
    """Exports all PublicationAuthor records to a timestamped JSON file."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"publication_authors_backup_{timestamp}.json")

    stmt = select(PublicationAuthor)
    result = await session.execute(stmt)
    records = result.scalars().all()

    backup_data = []
    for r in records:
        backup_data.append({
            "id": str(r.id),
            "publication_id": str(r.publication_id),
            "faculty_id": str(r.faculty_id),
            "author_position": r.author_position,
            "author_name_raw": r.author_name_raw,
            "is_corresponding": r.is_corresponding,
            "attribution_confidence": r.attribution_confidence,
            "attribution_method": r.attribution_method,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2)

    print(f"Backed up {len(backup_data)} PublicationAuthor records to: {backup_file}")
    return backup_file


async def run_reconciliation(dry_run: bool = False):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    async with async_session_factory() as session:
        print(f"Starting Attribution Reconciliation (dry_run={dry_run})...")
        
        # 1. Backup before modifying anything
        if not dry_run:
            await backup_publication_authors(session)

        attribution_agent = FacultyAttributionAgent(session)

        # 2. Fetch all active faculty
        faculty_stmt = select(FacultyProfile).options(
            selectinload(FacultyProfile.name_variants),
            selectinload(FacultyProfile.identifiers),
            selectinload(FacultyProfile.publication_links).selectinload(PublicationAuthor.publication).selectinload(Publication.sources),
        ).where(FacultyProfile.status == "active")

        faculty_res = await session.execute(faculty_stmt)
        faculty_list = faculty_res.scalars().unique().all()

        print(f"Loaded {len(faculty_list)} active faculty profiles.")

        audit_results = {}

        for profile in faculty_list:
            fac_id_str = str(profile.id)
            fac_name = profile.normalized_name
            fac_dept = profile.department

            high_conf = []
            ambiguous_candidates = []
            likely_wrong = []

            for link in profile.publication_links:
                pub = link.publication
                if not pub:
                    continue

                # Re-evaluate using remediated attribution scoring
                score, method, candidate_name = await attribution_agent.compute_faculty_pub_match(profile, pub)

                # Collect authors & affiliations info for reporting
                sources_info = []
                for s in pub.sources:
                    if s.raw_metadata:
                        sources_info.append(s.source_system)

                entry = {
                    "publication_id": str(pub.id),
                    "doi": pub.doi,
                    "title": pub.title,
                    "year": pub.publication_date.year if pub.publication_date else None,
                    "raw_author_name": link.author_name_raw or candidate_name,
                    "current_confidence": link.attribution_confidence,
                    "current_method": link.attribution_method,
                    "recomputed_score": score,
                    "recomputed_method": method,
                    "citations": pub.citation_count or 0,
                    "authors": pub.authors_raw or [],
                }

                if link.attribution_method == "human_confirmed":
                    # Retain explicitly confirmed records
                    high_conf.append(entry)
                elif score >= 0.95:
                    high_conf.append(entry)
                elif score >= 0.60:
                    ambiguous_candidates.append(entry)
                else:
                    likely_wrong.append(entry)

            # Compute current metrics
            current_pubs = len(profile.publication_links)
            current_cits = sum((l.publication.citation_count or 0) for l in profile.publication_links if l.publication)
            cits_list = sorted([(l.publication.citation_count or 0) for l in profile.publication_links if l.publication], reverse=True)
            current_h = sum(1 for i, c in enumerate(cits_list) if c >= i + 1)
            current_i10 = sum(1 for c in cits_list if c >= 10)

            # Compute corrected high-confidence metrics
            hc_cits_list = sorted([e["citations"] for e in high_conf], reverse=True)
            hc_pubs = len(high_conf)
            hc_cits = sum(e["citations"] for e in high_conf)
            hc_h = sum(1 for i, c in enumerate(hc_cits_list) if c >= i + 1)
            hc_i10 = sum(1 for c in hc_cits_list if c >= 10)

            audit_results[fac_id_str] = {
                "name": fac_name,
                "department": fac_dept,
                "current_pubs": current_pubs,
                "current_citations": current_cits,
                "current_h_index": current_h,
                "current_i10_index": current_i10,
                "high_conf_count": hc_pubs,
                "high_conf_citations": hc_cits,
                "high_conf_h_index": hc_h,
                "high_conf_i10_index": hc_i10,
                "ambiguous_count": len(ambiguous_candidates),
                "likely_wrong_count": len(likely_wrong),
                "high_conf": high_conf,
                "ambiguous_candidates": ambiguous_candidates,
                "likely_wrong": likely_wrong,
            }

            if not dry_run:
                # 1. Detach likely wrong and ambiguous candidates from PublicationAuthor
                to_detach_pub_ids = [uuid.UUID(e["publication_id"]) for e in likely_wrong + ambiguous_candidates]
                if to_detach_pub_ids:
                    del_stmt = delete(PublicationAuthor).where(
                        PublicationAuthor.faculty_id == profile.id,
                        PublicationAuthor.publication_id.in_(to_detach_pub_ids)
                    )
                    await session.execute(del_stmt)

                # 2. For ambiguous candidates, ensure ReviewTask(attribution_ambiguous) exists
                for cand in ambiguous_candidates:
                    pub_id = uuid.UUID(cand["publication_id"])
                    # Check if pending ReviewTask already exists
                    task_stmt = select(ReviewTask).where(
                        ReviewTask.task_type == "attribution_ambiguous",
                        ReviewTask.entity_id == pub_id,
                        ReviewTask.related_entity_id == profile.id,
                        ReviewTask.status == "pending"
                    )
                    existing_task = (await session.execute(task_stmt)).scalars().first()
                    if not existing_task:
                        new_task = ReviewTask(
                            id=uuid.uuid4(),
                            task_type="attribution_ambiguous",
                            priority="high",
                            status="pending",
                            entity_type="publication",
                            entity_id=pub_id,
                            related_entity_id=profile.id,
                            explanation=f"Ambiguous author match '{cand['raw_author_name']}' for faculty {profile.normalized_name} ({profile.department}) with score {cand['recomputed_score']:.2f}.",
                            evidence={
                                "match_score": cand["recomputed_score"],
                                "match_method": cand["recomputed_method"],
                                "raw_author_name": cand["raw_author_name"],
                                "title": cand["title"],
                                "doi": cand["doi"],
                                "faculty_name": profile.normalized_name,
                                "faculty_department": profile.department,
                            },
                            options=[
                                {"action": "CONFIRM", "label": "Confirm attribution (This is my publication)"},
                                {"action": "REJECT", "label": "Reject attribution (Not my publication)"},
                                {"action": "REASSIGN", "label": "Reassign to different faculty"},
                                {"action": "DEFER", "label": "Defer review"}
                            ],
                            agent_name="FacultyAttributionAgent",
                        )
                        session.add(new_task)

                # 3. For likely wrong publications, ensure any pending attribution tasks are cleaned/rejected
                for wrong in likely_wrong:
                    pub_id = uuid.UUID(wrong["publication_id"])
                    del_wrong_tasks = delete(ReviewTask).where(
                        ReviewTask.task_type == "attribution_ambiguous",
                        ReviewTask.entity_id == pub_id,
                        ReviewTask.related_entity_id == profile.id,
                        ReviewTask.status == "pending"
                    )
                    await session.execute(del_wrong_tasks)

        if not dry_run:
            await session.commit()
            print("Successfully reconciled PublicationAuthor links and ReviewTasks.")

            # 4. Recalculate Metrics for all faculty
            print("Recalculating metrics via MetricsAgent...")
            metrics_agent = MetricsAgent(session)
            # Re-process faculty metrics
            faculty_stmt_2 = select(FacultyProfile).options(
                selectinload(FacultyProfile.publication_links).selectinload(PublicationAuthor.publication)
            ).where(FacultyProfile.status == "active")
            fac_res_2 = await session.execute(faculty_stmt_2)
            for p in fac_res_2.scalars().unique().all():
                stats = {"faculty_snapshots": 0, "calculated_metrics": 0, "missing_metrics": 0, "errors": 0}
                await metrics_agent._process_faculty_metrics(p, stats)
            await session.commit()
            print("Metrics snapshots updated successfully.")

        # Print audit summary safely
        print("\n" + "="*80)
        print("RECONCILIATION AUDIT SUMMARY")
        print("="*80)
        for fac_id, r in audit_results.items():
            safe_name = r['name'].encode('ascii', errors='replace').decode('ascii')
            print(f"\nFaculty: {safe_name} ({r['department']}) [ID: {fac_id}]")
            print(f"  Current Links: {r['current_pubs']} pubs | {r['current_citations']} cits | h: {r['current_h_index']} | i10: {r['current_i10_index']}")
            print(f"  High Confidence: {r['high_conf_count']} pubs | {r['high_conf_citations']} cits | h: {r['high_conf_h_index']} | i10: {r['high_conf_i10_index']}")
            print(f"  Ambiguous Candidates (Review Required): {r['ambiguous_count']}")
            print(f"  Likely Wrong (Detached): {r['likely_wrong_count']}")
            if r['likely_wrong']:
                print("  Sample Likely Wrong Publications:")
                for w in r['likely_wrong'][:3]:
                    safe_title = (w['title'] or '')[:60].encode('ascii', errors='replace').decode('ascii')
                    safe_raw = (w['raw_author_name'] or '').encode('ascii', errors='replace').decode('ascii')
                    print(f"    - DOI: {w['doi']} | Title: {safe_title}... | Raw Author: {safe_raw} | Score: {w['recomputed_score']:.2f}")

        # Save complete audit report to JSON
        report_path = os.path.join(BACKUP_DIR, "reconciliation_audit_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(audit_results, f, indent=2)
        print(f"\nFull audit report saved to: {report_path}")

        return audit_results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run without mutating DB")
    args = parser.parse_args()
    asyncio.run(run_reconciliation(dry_run=args.dry_run))
