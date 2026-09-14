import csv
import re
from pathlib import Path

def normalize_name_for_match(name: str) -> str:
    # remove Dr, Mr, Ms, Prof, dots, extra spaces
    n = name.strip()
    n = re.sub(r'^(Dr\.|Dr|Mr\.|Mr|Ms\.|Ms|Prof\.|Prof)\s+', '', n, flags=re.IGNORECASE)
    n = n.replace('.', ' ')
    n = re.sub(r'\s+', ' ', n).strip().lower()
    return n

prof_csv = Path('data/raw/faculty_profiles.csv')
pub_csv = Path('data/raw/faculty_publications.csv')

with open(prof_csv, encoding='utf-8-sig') as f:
    prof_rows = list(csv.DictReader(f))

with open(pub_csv, encoding='utf-8') as f:
    pub_rows = list(csv.DictReader(f))

print(f"Total profiles: {len(prof_rows)}")
print(f"Total publication rows: {len(pub_rows)}")

prof_map = {}
for p in prof_rows:
    raw = p['Name'].strip()
    norm = normalize_name_for_match(raw)
    prof_map[norm] = raw
    print(f"Profile: '{raw}' -> normalized key: '{norm}'")

print("\nMatching Publication Rows to Profiles:")
matched = 0
unmatched = []
for i, r in enumerate(pub_rows):
    fac_name = r['Faculty Name'].strip()
    norm_fac = normalize_name_for_match(fac_name)
    
    # Try exact normalized match
    match = None
    if norm_fac in prof_map:
        match = prof_map[norm_fac]
    else:
        # Try substring or token match
        tokens = set(norm_fac.split())
        for pk, pv in prof_map.items():
            p_tokens = set(pk.split())
            if tokens == p_tokens or tokens.issubset(p_tokens) or p_tokens.issubset(tokens):
                match = pv
                break
            # check last name and first name overlap
            if len(tokens.intersection(p_tokens)) >= 2:
                match = pv
                break
    if match:
        matched += 1
    else:
        unmatched.append((i+1, fac_name))

print(f"\nMatched: {matched}/{len(pub_rows)}")
if unmatched:
    print(f"Unmatched rows ({len(unmatched)}):", set([u[1] for u in unmatched]))
