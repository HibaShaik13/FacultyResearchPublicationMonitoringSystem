import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import async_session_factory
from app.models.publication import Publication, PublicationSource, PublicationAuthor
from app.models.faculty import FacultyProfile
from app.models.review import ReviewTask
from app.agents.verification_agent import VerificationAgent
from sqlalchemy import select, delete

async def main():
    async with async_session_factory() as session:
        print("Checking publication sources...")
        pubs_res = await session.execute(select(Publication))
        pubs = pubs_res.scalars().all()
        
        sources_added = 0
        for p in pubs:
            # Check if source exists
            src_res = await session.execute(
                select(PublicationSource).where(PublicationSource.publication_id == p.id)
            )
            if not src_res.scalars().first():
                # Add csv_import source or crossref if DOI exists
                src = PublicationSource(
                    publication_id=p.id,
                    source_system="crossref" if p.doi else "csv_import",
                    source_id=p.doi or str(p.id)
                )
                session.add(src)
                sources_added += 1
                
        await session.commit()
        print(f"Added {sources_added} missing publication sources.")
        
        # Clean up orphaned review tasks
        print("Cleaning orphaned review tasks...")
        pub_ids = set((await session.execute(select(Publication.id))).scalars().all())
        fac_ids = set((await session.execute(select(FacultyProfile.id))).scalars().all())
        
        tasks_res = await session.execute(select(ReviewTask))
        tasks = tasks_res.scalars().all()
        
        deleted_count = 0
        for t in tasks:
            if t.entity_type == "publication" and t.entity_id not in pub_ids:
                await session.delete(t)
                deleted_count += 1
            elif t.entity_type == "faculty" and t.entity_id not in fac_ids:
                await session.delete(t)
                deleted_count += 1
                
        await session.commit()
        print(f"Cleaned {deleted_count} orphaned review tasks.")
        
        # Now run VerificationAgent
        print("Running VerificationAgent...")
        agent = VerificationAgent(session)
        stats = await agent.run()
        print("VerificationAgent Run Completed. Stats:", stats)

if __name__ == "__main__":
    asyncio.run(main())
