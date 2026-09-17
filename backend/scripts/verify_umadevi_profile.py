import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.services.identity_verification_service import IdentityVerificationService
from sqlalchemy import select


async def main():
    async with async_session_factory() as session:
        f = (await session.execute(
            select(FacultyProfile).where(FacultyProfile.raw_name.ilike('%umadevi%'))
        )).scalars().first()

        if not f:
            print("Dr. M. Umadevi not found")
            return

        service = IdentityVerificationService(session)
        status_data = await service.get_faculty_identifiers_status(f.id)
        print("Faculty ID:", f.id)
        print("Faculty Raw Name:", f.raw_name)
        print("Connected Count:", status_data["connected_count"])
        for ident in status_data["identifiers"]:
            print(f"  - {ident['name']}: value={ident['value']}, verified={ident['verified']}, status={ident['status']}, url={ident['profile_url']}")


if __name__ == "__main__":
    asyncio.run(main())
