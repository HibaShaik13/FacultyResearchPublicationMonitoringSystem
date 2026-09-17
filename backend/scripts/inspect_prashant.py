import asyncio
import json
import sys
import httpx

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.main import app

async def main():
    transport = httpx.ASGITransport(app=app)
    results = {}
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        fac_list = await client.get('/api/v1/faculty/?search=Prashant')
        data = fac_list.json().get('data', [])
        for fac in data:
            fid = fac['id']
            f_resp = await client.get(f'/api/v1/faculty/{fid}')
            d_resp = await client.get(f'/api/v1/analytics/dashboard?faculty_id={fid}')
            p_resp = await client.get(f'/api/v1/publications/?faculty_id={fid}')
            p_data = p_resp.json()
            results[fid] = {
                'profile': f_resp.json(),
                'dashboard': d_resp.json(),
                'publications_total': p_data.get('total'),
                'sample_publications': p_data.get('data', [])[:10]
            }

    with open('prashant_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    print("SAVED_PRASHANT_RESULTS")

if __name__ == "__main__":
    asyncio.run(main())

