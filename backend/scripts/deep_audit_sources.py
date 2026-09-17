import asyncio
import json
import uuid
from sqlalchemy import select
from app.database import async_session_factory
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from sqlalchemy.orm import selectinload

SIVA_ID = uuid.UUID('e7399ee0-758c-453b-8a96-329e3dc2cc96')

async def main():
    async with async_session_factory() as session:
        pas = (await session.execute(
            select(PublicationAuthor)
            .options(selectinload(PublicationAuthor.publication).selectinload(Publication.sources))
            .where(PublicationAuthor.faculty_id == SIVA_ID)
        )).scalars().all()

        detailed_audit = []

        for idx, pa in enumerate(pas, 1):
            pub = pa.publication
            all_parsed_authors = pub.authors_parsed or []
            
            # Extract all raw authors from sources
            source_authors = []
            for s in pub.sources:
                if s.raw_metadata and isinstance(s.raw_metadata, dict):
                    # Crossref author
                    cr_auths = s.raw_metadata.get("author") or []
                    for a in cr_auths:
                        if isinstance(a, dict):
                            name = f"{a.get('given', '')} {a.get('family', '')}".strip() or a.get("name", "")
                            affil = [af.get("name") for af in a.get("affiliation", []) if isinstance(af, dict) and af.get("name")]
                            source_authors.append({"name": name, "affiliations": affil, "source": s.source_system})
                    
                    # OpenAlex authorships
                    oa_auths = s.raw_metadata.get("authorships") or []
                    for a in oa_auths:
                        if isinstance(a, dict):
                            author_obj = a.get("author", {}) or {}
                            name = author_obj.get("display_name") or ""
                            oa_id = author_obj.get("id") or ""
                            orcid = author_obj.get("orcid") or ""
                            institutions = [inst.get("display_name") for inst in a.get("institutions", []) if isinstance(inst, dict) and inst.get("display_name")]
                            source_authors.append({
                                "name": name,
                                "openalex_id": oa_id,
                                "orcid": orcid,
                                "institutions": institutions,
                                "source": "openalex"
                            })

            # Check which author in source_authors actually matched Dr. P. Siva Prasad
            # Does any author contain "Siva", "Shiva", "Sai", "Prasad"?
            prasad_authors = []
            for sa in source_authors:
                n = sa.get("name", "").lower()
                if "prasad" in n or "siva" in n or "sai" in n or "shiva" in n:
                    prasad_authors.append(sa)

            detailed_audit.append({
                "index": idx,
                "pub_id": str(pub.id),
                "title": pub.title,
                "doi": pub.doi,
                "year": pub.year,
                "citation_count": pub.citation_count or 0,
                "pa_author_name_raw": pa.author_name_raw,
                "pa_attribution_method": pa.attribution_method,
                "pa_attribution_confidence": pa.attribution_confidence,
                "all_parsed_authors": all_parsed_authors,
                "prasad_authors_in_source": prasad_authors,
                "affiliation_text": pub.affiliation_text
            })

        with open("siva_author_metadata_deep_audit.json", "w", encoding="utf-8") as f:
            json.dump(detailed_audit, f, indent=2)

        print(f"Deep audit written for {len(detailed_audit)} publications.")

if __name__ == "__main__":
    asyncio.run(main())
