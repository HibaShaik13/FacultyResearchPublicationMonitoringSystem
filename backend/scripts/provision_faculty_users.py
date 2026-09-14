import asyncio
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

sys.path.insert(0, r"c:\Users\muska\OneDrive\Desktop\ResearchFacultyMonitoringSystem\backend")

from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.user import User
import uuid

from app.core.security import hash_password

async def provision_umadevi():
    async with async_session_factory() as db:
        # Find Umadevi
        query = select(FacultyProfile).where(FacultyProfile.raw_name.ilike("%umadevi%"))
        result = await db.execute(query)
        umadevi = result.scalars().first()
        
        if not umadevi:
            print("Umadevi not found!")
            return

        print(f"Found Umadevi: {umadevi.id}")

        email = umadevi.institutional_email or "druma_cse@vignan.ac.in"
        
        # Check if user exists
        user_query = select(User).where(User.email == email)
        existing = (await db.execute(user_query)).scalars().first()
        if existing:
            print("User already exists, updating...")
            existing.faculty_id = umadevi.id
            existing.role = "faculty"
            existing.password_hash = hash_password("password")
        else:
            print("Creating user...")
            new_user = User(
                id=uuid.uuid4(),
                email=email,
                password_hash=hash_password("password"),
                full_name=umadevi.raw_name,
                role="faculty",
                faculty_id=umadevi.id,
                is_active=True,
            )
            db.add(new_user)
            
        await db.commit()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(provision_umadevi())
