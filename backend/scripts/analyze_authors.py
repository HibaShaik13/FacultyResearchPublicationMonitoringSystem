import json

with open("siva_author_metadata_deep_audit.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total publications inspected: {len(data)}")

prasad_names_found = {}
sai_prasad_pubs = []
siva_prasad_pubs = []
other_prasad_pubs = []
no_prasad_pubs = []

for item in data:
    prasad_authors = item.get("prasad_authors_in_source") or []
    all_parsed = item.get("all_parsed_authors") or []
    
    # Collect all author names on this paper
    names_on_paper = [pa.get("name") for pa in prasad_authors if pa.get("name")]
    if not names_on_paper and all_parsed:
        for a in all_parsed:
            if isinstance(a, dict):
                n = a.get("name", "")
                if "prasad" in n.lower() or "siva" in n.lower() or "sai" in n.lower():
                    names_on_paper.append(n)

    if not names_on_paper:
        no_prasad_pubs.append(item)
    else:
        for n in names_on_paper:
            prasad_names_found[n] = prasad_names_found.get(n, 0) + 1
        
        has_sai = any("sai" in n.lower() for n in names_on_paper)
        has_siva = any("siva" in n.lower() or "shiva" in n.lower() for n in names_on_paper)
        
        if has_sai and not has_siva:
            sai_prasad_pubs.append(item)
        elif has_siva:
            siva_prasad_pubs.append(item)
        else:
            other_prasad_pubs.append(item)

print("\n--- AUTHOR NAMES FOUND ON PAPERS ---")
for name, cnt in sorted(prasad_names_found.items(), key=lambda x: x[1], reverse=True):
    print(f"  '{name}': {cnt}")

print(f"\n--- BREAKDOWN ---")
print(f"Papers with 'Sai Prasad' (and no Siva): {len(sai_prasad_pubs)}")
print(f"Papers with 'Siva/Shiva Prasad': {len(siva_prasad_pubs)}")
print(f"Papers with other 'Prasad' variants (e.g. S. Prasad, P. Prasad): {len(other_prasad_pubs)}")
print(f"Papers with NO Prasad-like author in source: {len(no_prasad_pubs)}")

print("\n--- SAMPLE 'Sai Prasad' PAPERS ---")
for p in sai_prasad_pubs[:5]:
    print(f"Title: {p['title'][:75]} | Year: {p['year']} | DOI: {p['doi']}")
    print(f"  Prasad Authors: {p['prasad_authors_in_source']}")
    print(f"  Affiliation: {p['affiliation_text']}")
    print()

print("\n--- SAMPLE 'Siva/Shiva Prasad' PAPERS ---")
for p in siva_prasad_pubs[:5]:
    print(f"Title: {p['title'][:75]} | Year: {p['year']} | DOI: {p['doi']}")
    print(f"  Prasad Authors: {p['prasad_authors_in_source']}")
    print(f"  Affiliation: {p['affiliation_text']}")
    print()

print("\n--- SAMPLE OTHER PRASAD PAPERS ---")
for p in other_prasad_pubs[:5]:
    print(f"Title: {p['title'][:75]} | Year: {p['year']} | DOI: {p['doi']}")
    print(f"  Prasad Authors: {p['prasad_authors_in_source']}")
    print(f"  Affiliation: {p['affiliation_text']}")
    print()
