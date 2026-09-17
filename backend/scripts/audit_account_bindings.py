import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory
from app.models.user import User
from app.models.faculty import FacultyProfile
from sqlalchemy import select


async def audit_bindings():
    async with async_session_factory() as session:
        users = (await session.execute(select(User))).scalars().all()
        faculty = (await session.execute(select(FacultyProfile))).scalars().all()

        print(f"=== AUDIT: {len(users)} USERS vs {len(faculty)} FACULTY PROFILES ===")
        print("\n--- ALL USERS IN DATABASE ---")
        for u in users:
            print(f"User ID: {u.id} | Email: {u.email} | Role: {u.role} | Full Name: {u.full_name} | Faculty ID: {u.faculty_id}")

        print("\n--- ALL FACULTY PROFILES IN DATABASE ---")
        for f in faculty:
            print(f"Faculty ID: {f.id} | Raw Name: {f.raw_name} | Dept: {f.department} | Email: {f.institutional_email or f.raw_email}")

        # Check bindings
        faculty_map = {f.id: f for f in faculty}
        email_map = {f.institutional_email.lower(): f for f in faculty if f.institutional_email}
        for f in faculty:
            if f.raw_email and f.raw_email.lower() not in email_map:
                email_map[f.raw_email.lower()] = f

        print("\n--- BINDING STATUS FOR USERS ---")
        for u in users:
            if u.role == "faculty":
                if u.faculty_id:
                    bound_fac = faculty_map.get(u.faculty_id)
                    if bound_fac:
                        print(f"[BOUND] User '{u.email}' ({u.full_name}) -> Faculty '{bound_fac.raw_name}' ({bound_fac.id})")
                    else:
                        print(f"[INVALID FK] User '{u.email}' has faculty_id={u.faculty_id} which does not exist in faculty_profiles!")
                else:
                    # Check if matching faculty exists by email
                    match = email_map.get(u.email.lower().strip())
                    if match:
                        print(f"[UNBOUND BUT MATCHABLE] User '{u.email}' ({u.full_name}) -> can match Faculty '{match.raw_name}' ({match.id})")
                    else:
                        print(f"[ORPHAN / UNBOUND] User '{u.email}' ({u.full_name}) -> NO matching FacultyProfile found!")
            else:
                print(f"[ADMIN ROLE] User '{u.email}' ({u.full_name}) | Role: {u.role}")



if __name__ == "__main__":
    asyncio.run(audit_bindings())
