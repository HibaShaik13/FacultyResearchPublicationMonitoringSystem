import asyncio
import os
import sys
import uuid
import httpx
from sqlalchemy import select, func

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from app.database import async_session_factory
from app.models.user import User
from app.models.faculty import FacultyProfile
from app.core.security import verify_password, decode_token
from app.seed.bootstrap import ensure_baseline_accounts
from app.main import app


async def run_deep_auth_tests():
    print("=" * 70)
    print("STEP 1: DATABASE ACCOUNT & BINDING VERIFICATION")
    print("=" * 70)

    async with async_session_factory() as session:
        # 1. Run idempotent ensure_baseline_accounts
        res = await ensure_baseline_accounts(session)
        print("ensure_baseline_accounts result:", res)

        # 2. Check Siva's user record
        siva_user = (await session.execute(select(User).where(func.lower(User.email) == 'drpsp_cse@vignan.ac.in'))).scalar_one_or_none()
        assert siva_user is not None, "Siva user must exist in database"
        print(f"User email: {siva_user.email}")
        print(f"User role: {siva_user.role}")
        print(f"User is_active: {siva_user.is_active}")
        print(f"User faculty_id: {siva_user.faculty_id}")

        # Check faculty profile
        siva_fp = (await session.execute(select(FacultyProfile).where(FacultyProfile.id == siva_user.faculty_id))).scalar_one_or_none()
        assert siva_fp is not None, "FacultyProfile must exist"
        print(f"Bound Faculty Profile: {siva_fp.raw_name} ({siva_fp.department})")
        assert str(siva_fp.id) == "e7399ee0-758c-453b-8a96-329e3dc2cc96"

        # Check password hash validity
        is_bcrypt = siva_user.password_hash.startswith("$2b$") or siva_user.password_hash.startswith("$2a$")
        print(f"Is bcrypt hash? {is_bcrypt}")
        assert is_bcrypt, "password_hash must be a valid bcrypt hash"

        # Check password verification
        pwd_match = verify_password("faculty123", siva_user.password_hash)
        print(f"Password 'faculty123' verification: {pwd_match}")
        assert pwd_match is True, "Password must match 'faculty123'"

    print("\n" + "=" * 70)
    print("STEP 2: HTTP LOGIN ENDPOINT TESTING (ASGI CLIENT)")
    print("=" * 70)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Faculty Login Success
        res_fac = await client.post("/api/v1/auth/login", data={"username": "drpsp_cse@vignan.ac.in", "password": "faculty123"})
        print("1. Faculty Login (drpsp_cse@vignan.ac.in / faculty123):", res_fac.status_code)
        assert res_fac.status_code == 200
        token_data = res_fac.json()
        assert "access_token" in token_data
        payload = decode_token(token_data["access_token"])
        print("   Token payload:", payload)
        assert payload["sub"] == "drpsp_cse@vignan.ac.in"
        assert payload["role"] == "faculty"

        # 2. Case-Insensitive Email Login
        res_case = await client.post("/api/v1/auth/login", data={"username": "DRPSP_CSE@VIGNAN.AC.IN", "password": "faculty123"})
        print("2. Case-Insensitive Login (DRPSP_CSE@...):", res_case.status_code)
        assert res_case.status_code == 200

        # 3. Admin Login Success
        res_adm = await client.post("/api/v1/auth/login", data={"username": "admin@vignan.ac.in", "password": "admin"})
        print("3. Admin Login (admin@vignan.ac.in / admin):", res_adm.status_code)
        assert res_adm.status_code == 200
        adm_payload = decode_token(res_adm.json()["access_token"])
        assert adm_payload["role"] == "research_admin"

        # 4. Invalid Password
        res_inv = await client.post("/api/v1/auth/login", data={"username": "drpsp_cse@vignan.ac.in", "password": "wrongpassword"})
        print("4. Invalid Password Response:", res_inv.status_code, res_inv.json())
        assert res_inv.status_code == 401
        assert res_inv.json()["detail"] == "Incorrect email or password"

        # 5. Missing Account
        res_miss = await client.post("/api/v1/auth/login", data={"username": "nonexistent@vignan.ac.in", "password": "faculty123"})
        print("5. Missing Account Response:", res_miss.status_code, res_miss.json())
        assert res_miss.status_code == 401
        assert res_miss.json()["detail"] == "Incorrect email or password"

        # 6. /me endpoint with Faculty Token
        fac_headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        res_me = await client.get("/api/v1/auth/me", headers=fac_headers)
        print("6. /api/v1/auth/me Profile:", res_me.status_code, res_me.json())
        assert res_me.status_code == 200
        assert res_me.json()["email"] == "drpsp_cse@vignan.ac.in"
        assert res_me.json()["faculty_id"] == "e7399ee0-758c-453b-8a96-329e3dc2cc96"

        # 7. Faculty Profile /me endpoint
        res_fac_me = await client.get("/api/v1/faculty/me", headers=fac_headers)
        print("7. /api/v1/faculty/me Research Profile:", res_fac_me.status_code)
        assert res_fac_me.status_code == 200
        assert res_fac_me.json()["id"] == "e7399ee0-758c-453b-8a96-329e3dc2cc96"

    print("\n" + "=" * 70)
    print("STEP 3: RECONCILIATION DRY-RUN & SAFETY ASSERTIONS")
    print("=" * 70)

    from scripts.reconcile_siva_production import reconcile_siva_prasad, verify_schema_integrity
    from app.models.faculty import FacultyIdentifier
    from app.models.publication import PublicationAuthor

    async with async_session_factory() as session:
        # Schema verification test
        await verify_schema_integrity(session)
        print("1. Schema verification: OK (All required tables present)")

        # Run dry run 1
        rep1 = await reconcile_siva_prasad(session, apply=False)
        print("2. First Dry Run Report:", rep1["faculty_profile"], rep1["user_account"])
        assert rep1["schema_verified"] is True
        assert rep1["openalex_rejected"] is True

        # Run dry run 2 (Idempotency test)
        rep2 = await reconcile_siva_prasad(session, apply=False)
        print("3. Second Dry Run (Idempotency):", rep2["faculty_profile"], rep2["user_account"])
        assert rep2["schema_verified"] is True

        # Identifier assertions
        siva_ids = (await session.execute(
            select(FacultyIdentifier).where(FacultyIdentifier.faculty_id == uuid.UUID("e7399ee0-758c-453b-8a96-329e3dc2cc96"))
        )).scalars().all()
        id_types = {i.identifier_type: i.identifier_value for i in siva_ids}
        print("4. Attached Identifiers:", id_types)
        assert "openalex" not in id_types or id_types.get("openalex") != "A5003901187", "OpenAlex A5003901187 must NOT be attached to Siva"

        # Attribution links
        pas = (await session.execute(
            select(PublicationAuthor).where(PublicationAuthor.faculty_id == uuid.UUID("e7399ee0-758c-453b-8a96-329e3dc2cc96"))
        )).scalars().all()
        pub_ids = [str(p.publication_id) for p in pas]
        print(f"5. Siva Verified Publication Links: {len(pas)} (Unique Pubs: {len(set(pub_ids))})")
        assert len(pas) == len(set(pub_ids)), "Must not have duplicate publication author links"

    print("\nALL AUTHENTICATION, SAFETY & RECONCILIATION TESTS PASSED (100% SUCCESS)!")


if __name__ == "__main__":
    asyncio.run(run_deep_auth_tests())
