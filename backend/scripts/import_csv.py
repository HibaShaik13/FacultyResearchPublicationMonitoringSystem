import asyncio
import csv
import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import engine, async_session_factory
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.metrics import FacultyMetricSnapshot
from sqlalchemy import select, delete

async def main():
    csv_file = os.path.join(os.path.dirname(__file__), '../../data/raw/faculty_publications.csv')
    
    async with async_session_factory() as session:
        # Clear existing publications to ensure ONLY the CSV data is shown as requested
        print("Clearing existing publications...")
        await session.execute(delete(PublicationSource))
        await session.execute(delete(PublicationAuthor))
        await session.execute(delete(Publication))
        
        # also reset metrics
        await session.execute(delete(FacultyMetricSnapshot))
        
        await session.commit()
        
        print(f"Reading CSV {csv_file}")
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                fac_name = row['Faculty Name'].strip()
                pub_text = row['Publication'].strip()
                date_str = row['Date'].strip()
                
                # Extract year
                year = None
                for part in date_str.split():
                    if part.isdigit() and len(part) == 4:
                        year = int(part)
                        break
                
                if not year and date_str[:4].isdigit():
                    year = int(date_str[:4])
                
                # Attempt to find faculty
                search_name = fac_name.replace('Dr ', '').replace('Dr. ', '').replace('Ms ', '').replace('Mr ', '')
                # Split to find first/last name
                parts = search_name.split()
                if len(parts) > 1:
                    last_name = parts[-1]
                    query = select(FacultyProfile).where(FacultyProfile.last_name.ilike(f"%{last_name}%"))
                else:
                    query = select(FacultyProfile).where((FacultyProfile.first_name + " " + FacultyProfile.last_name).ilike(f"%{search_name}%"))

                result = await session.execute(query)
                faculty = result.scalars().first()
                
                if not faculty:
                    print(f"Could not find faculty: {fac_name}")
                    continue
                
                # Try to extract DOI if present
                doi = None
                if "doi.org/" in pub_text:
                    doi = pub_text.split("doi.org/")[1].split()[0].rstrip(".")
                elif "DOI:" in pub_text:
                    doi = pub_text.split("DOI:")[1].split()[0].rstrip(".")
                
                new_pub = Publication(
                    title=pub_text[:500], # Storing raw text as title for now or just truncate
                    abstract="",
                    year=year,
                    doi=doi,
                    publication_type="journal-article",
                    journal_name="", normalized_title=pub_text[:500].lower(),
                    citation_count=0,
                    verification_status="verified",
                    risk_level="low"
                )
                session.add(new_pub)
                await session.flush()
                
                pub_author = PublicationAuthor(
                    publication_id=new_pub.id,
                    faculty_id=faculty.id,
                    author_position=1,
                    author_name_raw=fac_name,
                    is_corresponding=False,
                    attribution_confidence=1.0
                )
                session.add(pub_author)
                
                # Update metrics
                metric_query = select(FacultyMetricSnapshot).where(FacultyMetricSnapshot.faculty_id == faculty.id)
                m_result = await session.execute(metric_query)
                metrics = m_result.scalars().first()
                if not metrics:
                    from datetime import datetime
                    metrics = FacultyMetricSnapshot(
                        faculty_id=faculty.id,
                        snapshot_date=datetime.utcnow(),
                        total_publications=1,
                        total_citations=0,
                        h_index=0,
                        i10_index=0
                    )
                    session.add(metrics)
                else:
                    metrics.total_publications += 1
                
            await session.commit()
            print("Import completed.")

if __name__ == '__main__':
    asyncio.run(main())
