import asyncio
import json
import sys
import httpx

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.main import app
from app.core.security import create_access_token
from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.review import ReviewTask
from app.models.metrics import FacultyMetricSnapshot
from sqlalchemy import select

async def test_all():
    print("===================================================================")
    print("VERIFYING VERIFICATION QUEUE & AUTHENTICATION ENDPOINTS")
    print("===================================================================")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated request -> returns 401
        res_noauth = await client.get("/api/v1/review/stats")
        print(f"1. Unauthenticated GET /api/v1/review/stats -> Status: {res_noauth.status_code} (Expected: 401)")
        assert res_noauth.status_code == 401

        # 2. Dr. P. Siva Prasad authentication
        fac_id = "e7399ee0-758c-453b-8a96-329e3dc2cc96"
        siva_token = create_access_token(data={"sub": "drpsp_cse@vignan.ac.in", "role": "faculty", "faculty_id": fac_id})
        siva_headers = {"Authorization": f"Bearer {siva_token}"}

        # 3. Dr. P. Siva Prasad review stats
        res_stats = await client.get("/api/v1/review/stats", headers=siva_headers)
        print(f"2. Dr. P. Siva Prasad GET /api/v1/review/stats -> Status: {res_stats.status_code}")
        stats_data = res_stats.json()
        print("   Stats:", json.dumps(stats_data, indent=2))
        assert stats_data["pending"] >= 77

        # 4. Dr. P. Siva Prasad review queue
        res_queue = await client.get("/api/v1/review/queue?status=pending&limit=10", headers=siva_headers)
        print(f"3. Dr. P. Siva Prasad GET /api/v1/review/queue -> Status: {res_queue.status_code}")
        queue_data = res_queue.json()
        print(f"   Returned items: {len(queue_data.get('data', []))}, Total pending: {queue_data.get('total')}")
        
        # Verify review_actions_allowed
        first_item = queue_data["data"][0] if queue_data.get("data") else None
        if first_item:
            print(f"   First task type: {first_item['task_type']}")
            print(f"   First task review_actions_allowed: {first_item['review_actions_allowed']}")
            print(f"   First task explanation: {first_item['explanation']}")
            assert first_item["review_actions_allowed"] is True

        # 5. Security test: Dr. P. Siva Prasad cannot approve a review task belonging to another faculty
        async with async_session_factory() as session:
            other_task_stmt = select(ReviewTask).where(ReviewTask.related_entity_id != fac_id, ReviewTask.entity_id != fac_id).limit(1)
            other_task = (await session.execute(other_task_stmt)).scalars().first()
            if other_task:
                res_forbidden = await client.post(
                    f"/api/v1/review/{other_task.id}/decide",
                    json={"decision": "approve", "comment": "Unauthorized attempt"},
                    headers=siva_headers
                )
                print(f"4. Security Check: Dr. Siva Prasad deciding on other task ({other_task.id}) -> Status: {res_forbidden.status_code} (Expected: 403)")
                assert res_forbidden.status_code == 403

        # 6. Dashboard metrics check
        res_dash = await client.get(f"/api/v1/analytics/dashboard?faculty_id={fac_id}")
        dash_data = res_dash.json()
        print("\n5. Dr. P. Siva Prasad Dashboard Overview:")
        print(f"   Total Publications: {dash_data['total_publications']}")
        print(f"   Total Citations: {dash_data['total_citations']}")
        print(f"   h-index: {dash_data['h_index']}")
        print(f"   i10-index: {dash_data['i10_index']}")
        assert dash_data['total_publications'] == 90
        assert dash_data['total_citations'] == 913
        assert dash_data['h_index'] == 13
        assert dash_data['i10_index'] == 14

        print("\nALL VERIFICATION FLOW CHECKS PASSED PERFECTLY!")

if __name__ == "__main__":
    asyncio.run(test_all())
