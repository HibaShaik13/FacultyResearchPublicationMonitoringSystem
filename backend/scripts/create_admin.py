import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.future import select

from app.database import async_session_factory, Base
from app.models.user import User
from app.core.security import hash_password

async def main():
    # Patch SQLite for arrays/jsonb
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
    def visit_ARRAY(self, type_, **kw): return "JSON"
    def visit_JSONB(self, type_, **kw): return "JSON"
    SQLiteTypeCompiler.visit_ARRAY = visit_ARRAY
    SQLiteTypeCompiler.visit_JSONB = visit_JSONB
    
    engine = create_async_engine("sqlite+aiosqlite:///seed_test.db")
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    
    async with session_factory() as session:
        stmt = select(User).where(User.email == "admin@vignan.ac.in")
        result = await session.execute(stmt)
        user = result.scalars().first()
        
        if not user:
            print("Creating admin user...")
            new_user = User(
                email="admin@vignan.ac.in",
                password_hash=hash_password("admin"),
                full_name="Dr. Hiba",
                role="research_admin"
            )
            session.add(new_user)
            await session.commit()
            print("Admin user created.")
        else:
            print("Admin user already exists.")

if __name__ == "__main__":
    asyncio.run(main())
