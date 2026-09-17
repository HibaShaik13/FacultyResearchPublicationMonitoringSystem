import asyncio
import json
import sys
from uuid import UUID
import httpx

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.main import app

async def main():
    transport = httpx.ASGITransport(app=app)
    results = {}
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        # 1. Stats
        s = await client.get('/api/v1/publications/stats')
        results['stats'] = s.json()
        
        # 2. Target Faculty: Dr. Prashant Upadhyay
        target_id = '38e4c234-7d43-47af-8c08-980c6ca097ae'
        f = await client.get(f'/api/v1/faculty/{target_id}')
        d = await client.get(f'/api/v1/analytics/dashboard?faculty_id={target_id}')
        p = await client.get(f'/api/v1/publications/?faculty_id={target_id}')
        results['target_faculty'] = {
            'profile': f.json(),
            'dashboard': d.json(),
            'publications_total': p.json().get('total'),
            'sample_publications': p.json().get('data', [])[:5]
        }

        # 3. Other faculty members
        fac_list = await client.get('/api/v1/faculty/?limit=10')
        other_facs = [x for x in fac_list.json().get('data', []) if x['id'] != target_id][:3]
        results['other_faculty'] = []
        for ofac in other_facs:
            oid = ofac['id']
            f_resp = await client.get(f'/api/v1/faculty/{oid}')
            od = await client.get(f'/api/v1/analytics/dashboard?faculty_id={oid}')
            op = await client.get(f'/api/v1/publications/?faculty_id={oid}')
            results['other_faculty'].append({
                'name': ofac['raw_name'],
                'id': oid,
                'profile': f_resp.json(),
                'dashboard': od.json(),
                'publications_total': op.json().get('total'),
                'sample_publications': op.json().get('data', [])[:3]
            })

    with open('test_results_dump.json', 'w', encoding='utf-8') as out_f:
        json.dump(results, out_f, indent=2, default=str)
    print("SAVED_RESULTS_SUCCESSFULLY")

if __name__ == "__main__":
    asyncio.run(main())

