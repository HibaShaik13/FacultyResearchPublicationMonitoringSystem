import asyncio
import json
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, func, text, and_, or_
from app.database import async_session_factory
from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.review import ReviewTask
from app.models.metrics import FacultyMetricSnapshot
from sqlalchemy.orm import selectinload

SIVA_ID = uuid.UUID('e7399ee0-758c-453b-8a96-329e3dc2cc96')

async def run_audit():
    async with async_session_factory() as session:
        # 1. Fetch Faculty Profile
        fac = (await session.execute(
            select(FacultyProfile).where(FacultyProfile.id == SIVA_ID)
        )).scalars().first()

        identifiers = (await session.execute(
            select(FacultyIdentifier).where(FacultyIdentifier.faculty_id == SIVA_ID)
        )).scalars().all()

        print(f"=== FACULTY PROFILE: {fac.raw_name} ===")
        print(f"ID: {fac.id}")
        print(f"Dept: {fac.department}, Designation: {fac.designation}")
        print(f"Email: {fac.institutional_email}")
        print(f"Research Interests: {fac.research_interests}")
        print(f"Declared Pub Count: {fac.declared_publication_count}")
        print(f"Identifiers: {[(i.identifier_type, i.identifier_value) for i in identifiers]}")

        # 2. Fetch all 90 PublicationAuthor records for Siva
        pa_query = (
            select(PublicationAuthor)
            .options(
                selectinload(PublicationAuthor.publication).selectinload(Publication.sources)
            )
            .where(PublicationAuthor.faculty_id == SIVA_ID)
        )
        pas = (await session.execute(pa_query)).scalars().all()
        print(f"\nTotal PublicationAuthor links for Siva: {len(pas)}")

        audit_records = []
        
        # Classification buckets
        high_conf = []
        med_conf = []
        ambiguous = []
        likely_wrong = []

        for pa in pas:
            pub = pa.publication
            sources = pub.sources or []
            
            # Extract author list and raw names
            raw_matched_author = pa.author_name_raw or ""
            authors_parsed = pub.authors_parsed or []
            authors_raw_str = pub.authors_raw or ""
            
            # Look up matched author details from authors_parsed
            matched_parsed = None
            if isinstance(authors_parsed, list):
                for ap in authors_parsed:
                    if isinstance(ap, dict) and ap.get("name") and raw_matched_author:
                        if raw_matched_author.lower() in ap.get("name", "").lower() or ap.get("name", "").lower() in raw_matched_author.lower():
                            matched_parsed = ap
                            break

            # Affiliations from sources / publication
            pub_affils = []
            if pub.affiliation_text:
                pub_affils.append(pub.affiliation_text)
            for s in sources:
                if s.raw_metadata and isinstance(s.raw_metadata, dict):
                    # Check authors / affiliations in raw_metadata
                    auths = s.raw_metadata.get("authorships") or s.raw_metadata.get("author") or []
                    if isinstance(auths, list):
                        for a in auths:
                            if isinstance(a, dict):
                                insts = a.get("institutions") or a.get("affiliation") or []
                                if isinstance(insts, list):
                                    for inst in insts:
                                        if isinstance(inst, dict):
                                            display = inst.get("display_name") or inst.get("name")
                                            if display and display not in pub_affils:
                                                pub_affils.append(display)
                                        elif isinstance(inst, str) and inst not in pub_affils:
                                            pub_affils.append(inst)

            affil_str = " | ".join(pub_affils) if pub_affils else (pub.affiliation_text or "None recorded")

            # Source systems
            src_systems = list(set([s.source_system for s in sources]))
            
            # Evidence Analysis & Classification
            name_lower = raw_matched_author.lower().strip()
            
            # High confidence criteria:
            # Explicit "siva prasad", "shiva prasad", "p. siva prasad", "p. shiva prasad", "sivaprasad p"
            # AND NOT clearly another institution / domain contradiction
            has_siva = ("siva" in name_lower or "shiva" in name_lower or "s. prasad" in name_lower)
            has_sai = ("sai" in name_lower)
            has_sarkale = ("sarkale" in name_lower)
            has_asad = ("asad" in name_lower or "rashad" in name_lower)
            has_durga = ("durga" in name_lower)
            
            is_lara = "lara" in affil_str.lower()
            is_vfstr = "vignan's foundation" in affil_str.lower() or "vfstr" in affil_str.lower() or "deemed to be" in affil_str.lower()
            is_medical_vaccine = "vaccine" in pub.title.lower() or "covid" in pub.title.lower() or "sars-cov-2" in pub.title.lower() or "marek" in pub.title.lower()
            
            classification = "C" # default Ambiguous
            reason = ""

            if has_sai or (has_siva and is_lara and not is_vfstr):
                classification = "D"
                reason = f"Author is '{raw_matched_author}', affiliation is Lara Institute (different faculty identity Dr. P. Sai Prasad)."
            elif has_sarkale or has_asad or has_durga or "v. n. prasad" in name_lower or "c. prasad" in name_lower or "m. prasad" in name_lower or "k. s. rao" in name_lower:
                classification = "D"
                reason = f"Author is '{raw_matched_author}' (completely different surname/forename mismatch)."
            elif is_medical_vaccine and ("phase 1" in pub.title.lower() or "phase 2" in pub.title.lower() or "bbv152" in pub.title.lower()):
                classification = "D"
                reason = f"Medical clinical trial (BBV152 vaccine / Bharat Biotech), author matched loosely as Prasad (not VFSTR CSE/Math)."
            elif has_siva:
                if is_vfstr or "guntur" in affil_str.lower() or "vignan" in affil_str.lower() or "mathematics" in pub.title.lower() or "algebra" in pub.title.lower() or "cryptography" in pub.title.lower() or "machine learning" in pub.title.lower():
                    classification = "A"
                    reason = f"Author '{raw_matched_author}' matches Dr. P. Siva Prasad with aligned institutional/research context."
                else:
                    classification = "B"
                    reason = f"Author '{raw_matched_author}' contains Siva Prasad, but generic affiliation."
            elif name_lower in ["p. s. prasad", "p.s. prasad", "p s prasad", "prasad p s", "prasad, p. s."]:
                classification = "B"
                reason = f"Initials match 'P. S. Prasad', probable variant."
            elif "prasad" in name_lower:
                classification = "C"
                reason = f"Generic surname match '{raw_matched_author}' without explicit 'Siva' forename."
            else:
                classification = "D"
                reason = f"Unrelated author name '{raw_matched_author}'."

            record = {
                "id": str(pub.id),
                "title": pub.title,
                "doi": pub.doi,
                "year": pub.year,
                "matched_author": raw_matched_author,
                "attribution_method": pa.attribution_method,
                "attribution_confidence": pa.attribution_confidence,
                "author_position": pa.author_position,
                "publication_affiliation": affil_str[:120],
                "sources": src_systems,
                "citation_count": pub.citation_count or 0,
                "classification": classification,
                "reason": reason
            }
            audit_records.append(record)

            if classification == "A":
                high_conf.append(record)
            elif classification == "B":
                med_conf.append(record)
            elif classification == "C":
                ambiguous.append(record)
            elif classification == "D":
                likely_wrong.append(record)

        # 3. Check specific DOI: 10.1109/iciccs67901.2026.11502731
        target_doi_record = next((r for r in audit_records if r.get("doi") == "10.1109/iciccs67901.2026.11502731"), None)

        # 4. Secondary Metrics (High Confidence Only)
        high_citations = sum(r["citation_count"] for r in high_conf)
        high_cits_list = sorted([r["citation_count"] for r in high_conf], reverse=True)
        high_h_index = sum(1 for i, c in enumerate(high_cits_list) if c >= i + 1)
        high_i10_index = sum(1 for c in high_cits_list if c >= 10)

        # Also High + Medium
        hm_pubs = high_conf + med_conf
        hm_citations = sum(r["citation_count"] for r in hm_pubs)
        hm_cits_list = sorted([r["citation_count"] for r in hm_pubs], reverse=True)
        hm_h_index = sum(1 for i, c in enumerate(hm_cits_list) if c >= i + 1)
        hm_i10_index = sum(1 for c in hm_cits_list if c >= 10)

        # 5. Check ReviewTask pending status for Siva
        tasks = (await session.execute(
            select(ReviewTask)
            .where(
                or_(ReviewTask.related_entity_id == SIVA_ID, ReviewTask.entity_id == SIVA_ID),
                ReviewTask.status == 'pending'
            )
        )).scalars().all()

        # How many of the 90 publications currently in PublicationAuthor are ALSO in the 84 pending tasks?
        siva_pub_ids = set(str(pa.publication_id) for pa in pas)
        task_pub_ids = set(str(t.entity_id) for t in tasks)
        overlap = siva_pub_ids.intersection(task_pub_ids)

        summary = {
            "total_attributed": len(pas),
            "high_confidence_count": len(high_conf),
            "medium_confidence_count": len(med_conf),
            "ambiguous_count": len(ambiguous),
            "likely_wrong_count": len(likely_wrong),
            "current_metrics": {
                "publications": len(pas),
                "citations": sum(r["citation_count"] for r in audit_records),
                "h_index": 13,
                "i10_index": 14
            },
            "high_confidence_metrics": {
                "publications": len(high_conf),
                "citations": high_citations,
                "h_index": high_h_index,
                "i10_index": high_i10_index
            },
            "high_plus_medium_metrics": {
                "publications": len(hm_pubs),
                "citations": hm_citations,
                "h_index": hm_h_index,
                "i10_index": hm_i10_index
            },
            "target_doi_evidence": target_doi_record,
            "tasks_overlap_with_publication_authors": len(overlap),
            "tasks_total": len(tasks),
            "audit_records": audit_records
        }

        with open("siva_attribution_audit_report.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        print("\n=== AUDIT SUMMARY ===")
        print(f"Total Attributed: {len(pas)}")
        print(f"High Confidence (A): {len(high_conf)}")
        print(f"Medium Confidence (B): {len(med_conf)}")
        print(f"Ambiguous (C): {len(ambiguous)}")
        print(f"Likely Wrong / False Match (D): {len(likely_wrong)}")
        print(f"\nTarget DOI Record: {target_doi_record}")
        print(f"\nPending Tasks Total: {len(tasks)}, Overlap with PublicationAuthor: {len(overlap)}")

if __name__ == "__main__":
    asyncio.run(run_audit())
