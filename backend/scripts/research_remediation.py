import asyncio
import json
import uuid
from sqlalchemy import select, func
from app.database import async_session_factory
from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.affiliation import AffiliationVariant
from app.models.metrics import FacultyMetricSnapshot
from sqlalchemy.orm import selectinload

async def audit_all_faculty():
    async with async_session_factory() as session:
        # Check affiliation variants
        aff_vars = (await session.execute(select(AffiliationVariant))).scalars().all()
        print("=== AFFILIATION VARIANTS IN DB ===")
        for v in aff_vars:
            print(f"  Canonical: '{v.canonical_name}' -> Variant: '{v.variant_text}'")

        # Check all faculty profiles
        faculties = (await session.execute(
            select(FacultyProfile).options(
                selectinload(FacultyProfile.identifiers),
                selectinload(FacultyProfile.name_variants)
            ).order_by(FacultyProfile.raw_name)
        )).scalars().all()

        print(f"\n=== TOTAL FACULTY PROFILES: {len(faculties)} ===")
        faculty_audit = []

        for f in faculties:
            pas = (await session.execute(
                select(PublicationAuthor)
                .options(selectinload(PublicationAuthor.publication).selectinload(Publication.sources))
                .where(PublicationAuthor.faculty_id == f.id)
            )).scalars().all()

            # Check attribution breakdown for each faculty
            high_conf = 0
            med_conf = 0
            likely_wrong = 0
            total_cits = 0
            high_cits = 0
            
            f_norm = f.normalized_name.lower()
            f_raw = f.raw_name.lower().replace("dr.", "").replace("dr", "").replace("prof.", "").replace("prof", "").strip()
            f_last = (f.last_name or "").lower()
            f_first = (f.first_name or "").lower()

            for pa in pas:
                pub = pa.publication
                cits = pub.citation_count or 0
                total_cits += cits
                
                matched = (pa.author_name_raw or "").lower().strip()
                affil = (pub.affiliation_text or "").lower()
                
                # Check for obvious institution mismatches (e.g. Lara, Nirula, VITS Hyderabad if faculty is VFSTR)
                is_lara = "lara" in affil
                is_vits_hyd = "hyderabad" in affil or "deshmukhi" in affil or "nalgonda" in affil
                is_nirula = "nirula" in affil
                
                # Check forename match
                if matched and (f_raw in matched or matched in f_raw or (f_last in matched and f_first and f_first in matched)):
                    if is_lara or is_vits_hyd or is_nirula:
                        likely_wrong += 1
                    else:
                        high_conf += 1
                        high_cits += cits
                elif matched and f_last in matched:
                    if is_lara or is_vits_hyd or is_nirula:
                        likely_wrong += 1
                    else:
                        med_conf += 1
                else:
                    likely_wrong += 1

            faculty_audit.append({
                "faculty_id": str(f.id),
                "name": f.raw_name,
                "dept": f.department,
                "identifiers": [(i.identifier_type, i.identifier_value) for i in f.identifiers],
                "current_attributed": len(pas),
                "high_conf": high_conf,
                "med_conf": med_conf,
                "likely_wrong": likely_wrong,
                "current_citations": total_cits,
                "high_confidence_citations": high_cits
            })

        print(f"\n{'Faculty Name':<35} | {'Dept':<6} | {'Total':<5} | {'High':<5} | {'Med':<5} | {'Wrong':<5} | {'CurCits':<7} | {'HighCits':<8}")
        print("-" * 95)
        for fa in faculty_audit:
            print(f"{fa['name']:<35} | {fa['dept'] or 'N/A':<6} | {fa['current_attributed']:<5} | {fa['high_conf']:<5} | {fa['med_conf']:<5} | {fa['likely_wrong']:<5} | {fa['current_citations']:<7} | {fa['high_confidence_citations']:<8}")

        with open("global_faculty_attribution_audit.json", "w", encoding="utf-8") as out:
            json.dump(faculty_audit, out, indent=2)

if __name__ == "__main__":
    asyncio.run(audit_all_faculty())
