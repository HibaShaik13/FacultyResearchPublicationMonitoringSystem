import asyncio
import json
import uuid
from sqlalchemy import select
from app.database import async_session_factory
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.faculty import FacultyProfile
from sqlalchemy.orm import selectinload

SIVA_ID = uuid.UUID('e7399ee0-758c-453b-8a96-329e3dc2cc96')

async def main():
    async with async_session_factory() as session:
        pas = (await session.execute(
            select(PublicationAuthor)
            .options(selectinload(PublicationAuthor.publication).selectinload(Publication.sources))
            .where(PublicationAuthor.faculty_id == SIVA_ID)
        )).scalars().all()

        classified_records = []
        
        counts = {"A": 0, "B": 0, "C": 0, "D": 0}

        for idx, pa in enumerate(pas, 1):
            pub = pa.publication
            
            # Find the author on the paper that matched Siva
            matched_name = pa.author_name_raw or "Unknown"
            
            # Find all authors from Crossref/OpenAlex/Parsed
            sources = pub.sources or []
            cr_authors = []
            oa_authors = []
            for s in sources:
                if s.raw_metadata:
                    if s.source_system == "crossref":
                        for a in s.raw_metadata.get("author", []):
                            n = f"{a.get('given', '')} {a.get('family', '')}".strip() or a.get("name", "")
                            affs = [af.get("name") for af in a.get("affiliation", []) if isinstance(af, dict) and af.get("name")]
                            cr_authors.append({"name": n, "affiliations": affs})
                    elif s.source_system == "openalex":
                        for a in s.raw_metadata.get("authorships", []):
                            n = a.get("author", {}).get("display_name", "")
                            insts = [inst.get("display_name") for inst in a.get("institutions", []) if isinstance(inst, dict) and inst.get("display_name")]
                            oa_authors.append({"name": n, "institutions": insts, "orcid": a.get("author", {}).get("orcid")})

            # Identify the specific author entity that triggered the match
            all_paper_authors = cr_authors or oa_authors
            
            # Affiliation of matched author / paper
            affil_list = []
            for a in all_paper_authors:
                if any(k in a["name"].lower() for k in ["siva", "shiva", "sai", "prasad"]):
                    affs = a.get("affiliations") or a.get("institutions") or []
                    affil_list.extend(affs)
            
            pub_affil = " | ".join(set(affil_list)) if affil_list else (pub.affiliation_text or "Not recorded in source")

            matched_lower = matched_name.lower()
            
            # Strict Classification Logic based on real evidence
            # Faculty Target: Dr. P. Siva Prasad (CSE / Mathematics, VFSTR Vadlamudi)
            
            # Criteria D: False Matches / Other people
            # 1. Author is explicitly Sai Prasad (Dr. P. Sai Prasad at Lara)
            # 2. Author is from a completely different institute (Lara, VITS Hyderabad EEE, Nirula, or medical/vaccine trials like Bharat Biotech BBV152)
            # 3. Author forename is completely different (S. Deva Prasad, Vara Prasad, Durga Prasad, Bhanu Prasad, Ram Prasad, Syam Prasad, Prasad Sarkale, etc.)
            
            is_explicit_siva = ("siva prasad" in matched_lower or "shiva prasad" in matched_lower or matched_lower == "p. siva prasad")
            has_sai = "sai" in matched_lower
            is_other_first_name = any(other in matched_lower for other in [
                "deva", "durga", "ram", "syam", "bhanu", "sarkale", "lalith", "rohit", "bharat", "ganesh", "eppe", "anjaneya", "eswara", "kiran", "deepika", "sravanthi", "mouli", "kanaka", "koteswara", "balakrishna", "krishna"
            ])
            
            is_lara = "lara" in pub_affil.lower()
            is_vfstr = "vignan's foundation" in pub_affil.lower() or "vfstr" in pub_affil.lower() or "vadlamudi" in pub_affil.lower() or "deemed to be" in pub_affil.lower()
            is_medical_vaccine = any(term in pub.title.lower() for term in ["sars-cov-2", "vaccine", "bbv152", "marek", "sorghum", "forage", "cropp"])

            classification = "C"
            reason = ""

            if has_sai or is_lara:
                classification = "D"
                reason = f"False match: Author is '{matched_name}' affiliated with Vignan's Lara Institute (different faculty Dr. P. Sai Prasad)."
            elif is_other_first_name:
                classification = "D"
                reason = f"False match: Author is '{matched_name}' (forename/individual mismatch)."
            elif is_medical_vaccine:
                classification = "D"
                reason = f"False match: Medical/Agricultural paper without CSE/Math connection, matched generic Prasad."
            elif is_explicit_siva:
                if is_vfstr or "cse" in pub_affil.lower() or "guntur" in pub_affil.lower() or "mathematics" in pub.title.lower() or "algebra" in pub.title.lower():
                    classification = "A"
                    reason = f"High confidence: Exact name '{matched_name}' with matching VFSTR/CSE/Math institutional affiliation."
                else:
                    classification = "B"
                    reason = f"Medium confidence: Author is '{matched_name}', but affiliation is generic or unrecorded."
            elif matched_lower in ["p. s. prasad", "s. prasad", "p. prasad"]:
                classification = "C"
                reason = f"Ambiguous: Initial/abbreviated author '{matched_name}' without explicit forename confirmation."
            else:
                classification = "D"
                reason = f"False match: Unrelated author '{matched_name}'."

            counts[classification] += 1

            classified_records.append({
                "index": idx,
                "title": pub.title,
                "doi": pub.doi,
                "year": pub.year,
                "matched_author": matched_name,
                "position": pa.author_position,
                "pub_affiliation": pub_affil,
                "sources": [s.source_system for s in sources],
                "citations": pub.citation_count or 0,
                "confidence_score": pa.attribution_confidence,
                "classification": classification,
                "reason": reason
            })

        # Calculate metrics for High Confidence only (A)
        high_conf_records = [r for r in classified_records if r["classification"] == "A"]
        high_pubs = len(high_conf_records)
        high_cits = sum(r["citations"] for r in high_conf_records)
        high_cits_list = sorted([r["citations"] for r in high_conf_records], reverse=True)
        high_h = sum(1 for i, c in enumerate(high_cits_list) if c >= i + 1)
        high_i10 = sum(1 for c in high_cits_list if c >= 10)

        # Calculate metrics for High + Medium (A + B)
        ab_records = [r for r in classified_records if r["classification"] in ["A", "B"]]
        ab_pubs = len(ab_records)
        ab_cits = sum(r["citations"] for r in ab_records)
        ab_cits_list = sorted([r["citations"] for r in ab_records], reverse=True)
        ab_h = sum(1 for i, c in enumerate(ab_cits_list) if c >= i + 1)
        ab_i10 = sum(1 for c in ab_cits_list if c >= 10)

        output = {
            "summary_counts": counts,
            "metrics_comparison": {
                "current_stored": {
                    "publications": len(pas),
                    "citations": sum(r["citations"] for r in classified_records),
                    "h_index": 13,
                    "i10_index": 14
                },
                "high_confidence_only_A": {
                    "publications": high_pubs,
                    "citations": high_cits,
                    "h_index": high_h,
                    "i10_index": high_i10
                },
                "high_plus_medium_AB": {
                    "publications": ab_pubs,
                    "citations": ab_cits,
                    "h_index": ab_h,
                    "i10_index": ab_i10
                }
            },
            "records": classified_records
        }

        with open("complete_attribution_audit.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        print("=== FINAL ATTRIBUTION AUDIT RESULTS ===")
        print(f"Total Attributed: {len(pas)}")
        print(f"Classification Breakdown: {counts}")
        print("\nMetrics Comparison:")
        print("  Current Stored:        ", output["metrics_comparison"]["current_stored"])
        print("  High Confidence (A):   ", output["metrics_comparison"]["high_confidence_only_A"])
        print("  High + Medium (A + B): ", output["metrics_comparison"]["high_plus_medium_AB"])

        print("\nHigh Confidence Publications Sample:")
        for r in high_conf_records[:5]:
            print(f"  [{r['classification']}] {r['title'][:70]} (Year: {r['year']}, Citations: {r['citations']}, Matched: '{r['matched_author']}', Affil: {r['pub_affiliation'][:60]})")

        print("\nLikely Wrong Publications Sample:")
        for r in [rec for rec in classified_records if rec["classification"] == "D"][:5]:
            print(f"  [{r['classification']}] {r['title'][:70]} (Year: {r['year']}, Citations: {r['citations']}, Matched: '{r['matched_author']}', Reason: {r['reason'][:60]})")

if __name__ == "__main__":
    asyncio.run(main())
