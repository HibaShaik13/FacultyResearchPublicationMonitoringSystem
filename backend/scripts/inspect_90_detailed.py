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

        records = []
        matched_name_counter = {}

        for idx, pa in enumerate(pas, 1):
            pub = pa.publication
            matched_name = pa.author_name_raw or "UNKNOWN"
            matched_name_counter[matched_name] = matched_name_counter.get(matched_name, 0) + 1
            
            # Find author entry in authors_parsed
            author_details = None
            if pub.authors_parsed and isinstance(pub.authors_parsed, list):
                for a in pub.authors_parsed:
                    if isinstance(a, dict):
                        name = a.get("name", "")
                        if matched_name.lower() in name.lower() or name.lower() in matched_name.lower():
                            author_details = a
                            break

            rec = {
                "index": idx,
                "pub_id": str(pub.id),
                "title": pub.title,
                "doi": pub.doi,
                "year": pub.year,
                "citation_count": pub.citation_count or 0,
                "matched_author_name": matched_name,
                "attribution_method": pa.attribution_method,
                "attribution_confidence": pa.attribution_confidence,
                "author_position": pa.author_position,
                "affiliation_text": pub.affiliation_text,
                "author_details_parsed": author_details,
                "sources": [s.source_system for s in pub.sources]
            }
            records.append(rec)

        summary = {
            "total": len(records),
            "matched_names_summary": matched_name_counter,
            "records": records
        }

        with open("siva_90_detailed_dump.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        print(f"Total records dumped: {len(records)}")
        print("\nMatched names frequency across the 90 publications:")
        for name, count in sorted(matched_name_counter.items(), key=lambda x: x[1], reverse=True):
            print(f"  '{name}': {count}")

if __name__ == "__main__":
    asyncio.run(main())
