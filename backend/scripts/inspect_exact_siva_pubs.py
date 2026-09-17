import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor

async def find_siva_pubs():
    async with async_session_factory() as session:
        fac_stmt = select(FacultyProfile).where(FacultyProfile.normalized_name.ilike("%siva prasad%"))
        fac = (await session.execute(fac_stmt)).scalars().first()

        stmt = select(PublicationAuthor).options(
            selectinload(PublicationAuthor.publication).selectinload(Publication.sources)
        ).where(PublicationAuthor.faculty_id == fac.id)
        links = (await session.execute(stmt)).scalars().all()

        print(f"Total links for {fac.normalized_name}: {len(links)}")
        for link in links:
            pub = link.publication
            # check all sources and raw metadata for Siva Prasad and VFSTR
            found_siva = False
            for s in pub.sources:
                meta = s.raw_metadata or {}
                meta_str = str(meta).lower()
                if "siva prasad" in meta_str or "shiva prasad" in meta_str or "siva" in str(pub.authors_raw).lower():
                    found_siva = True
            if found_siva or "siva" in (pub.authors_raw or "").lower():
                print(f"Pub {pub.id}: {pub.title[:60]} | DOI: {pub.doi} | Citations: {pub.citation_count}")
                for s in pub.sources:
                    if s.source_system == "openalex":
                        authorships = s.raw_metadata.get("authorships", [])
                        for a in authorships:
                            dname = a.get("author", {}).get("display_name", "")
                            if "siva" in dname.lower() or "prasad" in dname.lower():
                                insts = [i.get("display_name") for i in a.get("institutions", [])]
                                print(f"    OpenAlex: {dname} @ {insts}")
                    elif s.source_system == "crossref":
                        for a in s.raw_metadata.get("author", []):
                            given = a.get("given", "")
                            family = a.get("family", "")
                            if "siva" in given.lower() or "siva" in family.lower() or "prasad" in family.lower():
                                print(f"    Crossref: {given} {family} @ {a.get('affiliation', [])}")

if __name__ == "__main__":
    asyncio.run(find_siva_pubs())
