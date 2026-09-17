import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor
from app.agents.attribution_agent import FacultyAttributionAgent

async def inspect_siva():
    async with async_session_factory() as session:
        agent = FacultyAttributionAgent(session)
        await agent._load_faculty()
        await agent._load_affiliation_keywords()

        # Find Siva
        fac = next((f for f in agent.faculty_cache if "siva prasad" in f.normalized_name), None)
        print(f"Faculty: {fac.normalized_name} (raw: {fac.raw_name})")
        print(f"Variants: {[v.name_variant for v in fac.name_variants]}")
        print(f"Identifiers: {[f'{i.identifier_type}:{i.identifier_value}' for i in fac.identifiers]}")

        stmt = select(PublicationAuthor).options(
            selectinload(PublicationAuthor.publication).selectinload(Publication.sources)
        ).where(PublicationAuthor.faculty_id == fac.id)
        links = (await session.execute(stmt)).scalars().all()
        print(f"Total links: {len(links)}")

        for i, link in enumerate(links):
            pub = link.publication
            score, method, cname = await agent.compute_faculty_pub_match(fac, pub)
            candidates = agent._parse_author_candidates(pub)
            if score >= 0.60 or "siva" in pub.title.lower() or i < 15:
                print(f"\n--- Pub #{i+1}: {pub.title[:50]} ---")
                print(f"  DOI: {pub.doi}")
                print(f"  Score: {score:.2f} | Method: {method} | Matched Candidate: {cname}")
                print(f"  Affiliation Text: {pub.affiliation_text}")
                print(f"  Parsed Candidates: {[{k: v for k, v in c.items() if k in ['name', 'affiliations', 'orcid']} for c in candidates[:3]]}")

if __name__ == "__main__":
    asyncio.run(inspect_siva())
