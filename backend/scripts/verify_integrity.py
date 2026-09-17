import asyncio
import sys
from sqlalchemy import select, func

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.metrics import FacultyMetricSnapshot

async def verify():
    async with async_session_factory() as session:
        stmt = select(FacultyProfile.raw_name, FacultyProfile.department, FacultyProfile.institutional_email).order_by(FacultyProfile.raw_name)
        res = await session.execute(stmt)
        faculty_list = res.all()
        print(f"Total Faculty in Database: {len(faculty_list)}")
        for i, (name, dept, email) in enumerate(faculty_list, 1):
            print(f"{i:2d}. {name} | {dept} | {email}")

        # Check existing key faculty metrics
        print("\nChecking sample existing faculty metrics:")
        for name in ["Dr. Prashant Upadhyay", "Dr. M. Umadevi", "Dr. S. N. Tirumala Rao"]:
            f_stmt = select(FacultyProfile).where(FacultyProfile.raw_name == name)
            f_res = await session.execute(f_stmt)
            f = f_res.scalars().first()
            if f:
                s_stmt = select(FacultyMetricSnapshot).where(FacultyMetricSnapshot.faculty_id == f.id).order_by(FacultyMetricSnapshot.snapshot_date.desc())
                s_res = await session.execute(s_stmt)
                s = s_res.scalars().first()
                if s:
                    print(f"  {name}: {s.total_publications} pubs, {s.total_citations} cits, h-index={s.h_index}, i10-index={s.i10_index}")

if __name__ == "__main__":
    asyncio.run(verify())
