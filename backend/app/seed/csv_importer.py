import csv
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.faculty import FacultyNameVariant, FacultyProfile

logger = logging.getLogger(__name__)


class FacultyCSVParser:
    """Parses and normalizes faculty profiles from CSV."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def _calculate_hash(self, row: Dict[str, str]) -> str:
        """Calculate a SHA-256 hash of the row for idempotency."""
        row_str = json.dumps(row, sort_keys=True)
        return hashlib.sha256(row_str.encode("utf-8")).hexdigest()

    def _normalize_name(self, raw_name: str) -> Tuple[str, str, str, str, str]:
        """
        Parses raw name into prefix, normalized name, first name, last name.
        Returns:
            title_prefix, normalized_name, first_name, last_name, cleaned_raw_name
        """
        name = raw_name.strip()
        # Remove leading/trailing dots
        name = name.strip(".")
        # Replace multiple spaces
        name = re.sub(r"\s+", " ", name)

        title_prefix = ""
        lower_name = name.lower()
        
        # Extract titles
        for title in ["dr.", "dr", "mr.", "mr", "ms.", "ms", "prof.", "prof"]:
            if lower_name.startswith(title + " "):
                # Get the actual matched casing from original string
                match_len = len(title)
                title_prefix = name[:match_len].strip(".")
                name = name[match_len:].strip()
                name = name.strip(".")
                break

        # Capitalize words properly instead of ALL CAPS
        name_parts = [part.capitalize() for part in name.split()]
        normalized_name = " ".join(name_parts)

        # Basic first/last split
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        return title_prefix.capitalize() if title_prefix else "", normalized_name, first_name, last_name, raw_name.strip()

    def _infer_department(self, email: str) -> str:
        """Infers department from institutional email."""
        email = email.lower().strip()
        if not email.endswith("@vignan.ac.in"):
            return "Unknown"
        
        prefix = email.split("@")[0]
        if "_cse" in prefix:
            return "CSE"
        elif "_eee" in prefix:
            return "EEE"
        elif "_mech" in prefix:
            return "MECH"
        elif "_acse" in prefix:
            return "ACSE"
        return "Unknown"

    def _parse_list(self, raw_str: str) -> List[str]:
        """Parses pipe-delimited list."""
        if not raw_str:
            return []
        parts = raw_str.split("|")
        return [p.strip() for p in parts if p.strip()]

    def parse(self) -> List[Dict[str, Any]]:
        """Parses the CSV and yields normalized records."""
        records = []
        with open(self.file_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    title, norm_name, fname, lname, clean_raw_name = self._normalize_name(row.get("Name", ""))
                    email = row.get("Email", "").strip()
                    dept = self._infer_department(email)
                    
                    pub_count_str = row.get("Publications Count", "0").strip()
                    try:
                        pub_count = int(pub_count_str) if pub_count_str else 0
                    except ValueError:
                        pub_count = 0

                    record = {
                        "raw_name": clean_raw_name,
                        "raw_designation": row.get("Title", "").strip(),
                        "raw_email": email,
                        "raw_phone": row.get("Phone", "").strip(),
                        
                        "normalized_name": norm_name.lower(),
                        "first_name": fname,
                        "last_name": lname,
                        "title_prefix": title,
                        
                        "department": dept,
                        "designation": row.get("Title", "").strip().title(),
                        "institutional_email": email if "@vignan.ac.in" in email.lower() else None,
                        "phone": row.get("Phone", "").strip(),
                        
                        "research_interests": self._parse_list(row.get("Research Interests", "")),
                        "education": {"raw": row.get("Education", "")}, # simplified for now
                        "academic_experience": row.get("Academic Experience", "").strip(),
                        "awards": row.get("Awards", "").strip(),
                        "memberships": row.get("Memberships", "").strip(),
                        "teaching_engagements": row.get("Teaching Engagements", "").strip(),
                        "research_summary": row.get("Research", "").strip(),
                        "administrative_positions": row.get("Administrative Positions", "").strip(),
                        "events": row.get("Events", "").strip(),
                        
                        "csv_row_hash": self._calculate_hash(row),
                        "source_file": "faculty_profiles.csv",
                        "declared_publication_count": pub_count,
                    }
                    records.append(record)
                except Exception as e:
                    logger.error(f"Error parsing row {row.get('Name')}: {e}")
        return records


class FacultyImporter:
    """Handles importing normalized faculty records into the database."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _generate_name_variants(self, first_name: str, last_name: str) -> List[str]:
        variants = set()
        if not first_name:
            return []
        
        # F Lastname
        variants.add(f"{first_name} {last_name}".strip())
        variants.add(f"{last_name} {first_name}".strip())
        
        if len(first_name) > 0:
            variants.add(f"{first_name[0]} {last_name}".strip())
            variants.add(f"{last_name} {first_name[0]}".strip())
            
        return [v for v in variants if v]

    async def run(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Runs the import process."""
        stats = {
            "total_processed": 0,
            "imported": 0,
            "skipped_duplicates": 0,
            "variants_created": 0,
            "errors": 0
        }

        for record in records:
            stats["total_processed"] += 1
            try:
                # Check for duplicate by hash or email
                stmt = select(FacultyProfile).where(
                    (FacultyProfile.csv_row_hash == record["csv_row_hash"]) |
                    ((FacultyProfile.institutional_email == record["institutional_email"]) & (record["institutional_email"] != None))
                )
                result = await self.session.execute(stmt)
                existing = result.scalars().first()

                if existing:
                    stats["skipped_duplicates"] += 1
                    continue

                # Create profile
                profile = FacultyProfile(
                    raw_name=record["raw_name"],
                    raw_designation=record["raw_designation"],
                    raw_email=record["raw_email"],
                    raw_phone=record["raw_phone"],
                    
                    normalized_name=record["normalized_name"],
                    first_name=record["first_name"],
                    last_name=record["last_name"],
                    title_prefix=record["title_prefix"],
                    
                    department=record["department"],
                    designation=record["designation"],
                    institutional_email=record["institutional_email"],
                    phone=record["phone"],
                    
                    research_interests=record["research_interests"],
                    education=record["education"],
                    academic_experience=record["academic_experience"],
                    awards=record["awards"],
                    memberships=record["memberships"],
                    teaching_engagements=record["teaching_engagements"],
                    research_summary=record["research_summary"],
                    administrative_positions=record["administrative_positions"],
                    events=record["events"],
                    
                    csv_row_hash=record["csv_row_hash"],
                    source_file=record["source_file"],
                    declared_publication_count=record["declared_publication_count"],
                    status="active"
                )
                self.session.add(profile)
                await self.session.flush() # get ID

                # Add variants
                variants = self._generate_name_variants(record["first_name"], record["last_name"])
                # Add normalized full name as base variant
                variants.append(f"{record['first_name']} {record['last_name']}".strip())
                
                # Make unique case-insensitive
                unique_variants = list(set([v.lower() for v in variants]))
                
                for var in unique_variants:
                    nv = FacultyNameVariant(
                        faculty_id=profile.id,
                        name_variant=var,
                        variant_source="csv_parse",
                        is_confirmed=True
                    )
                    self.session.add(nv)
                    stats["variants_created"] += 1

                stats["imported"] += 1

            except Exception as e:
                logger.error(f"Error importing {record.get('raw_name')}: {e}")
                stats["errors"] += 1
                await self.session.rollback()
                continue
                
        await self.session.commit()
        return stats


class PublicationCSVParser:
    """Parses and normalizes publications from faculty_publications.csv."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def _calculate_hash(self, row: Dict[str, str]) -> str:
        """Calculate a SHA-256 hash of the row for idempotency."""
        row_str = json.dumps(row, sort_keys=True)
        return hashlib.sha256(row_str.encode("utf-8")).hexdigest()

    def _extract_doi(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract DOI and DOI URL if present in the text."""
        # Check standard DOI patterns
        # 1. URLs
        m_url = re.search(r'https?://(?:dx\.)?doi\.org/([^\s,;"]+)', text, re.IGNORECASE)
        if m_url:
            doi = m_url.group(1).rstrip(".")
            return doi, m_url.group(0).rstrip(".")
        
        # 2. DOI: 10.xxxx
        m_prefix = re.search(r'(?:DOI:?\s*|doi:?\s*)(10\.\d{4,9}/[^\s,;"]+)', text, re.IGNORECASE)
        if m_prefix:
            doi = m_prefix.group(1).rstrip(".")
            return doi, f"https://doi.org/{doi}"

        # 3. Direct 10.xxxx pattern
        m_direct = re.search(r'\b(10\.\d{4,9}/[^\s,;"]+)', text)
        if m_direct:
            doi = m_direct.group(1).rstrip(".")
            return doi, f"https://doi.org/{doi}"

        return None, None

    def _extract_year_and_date(self, date_str: str, pub_text: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        """Extract year, month, and date string."""
        year = None
        month = None
        
        # Months map
        months_map = {
            "january": 1, "jan": 1,
            "february": 2, "feb": 2,
            "march": 3, "mar": 3,
            "april": 4, "apr": 4,
            "may": 5,
            "june": 6, "jun": 6,
            "july": 7, "jul": 7,
            "august": 8, "aug": 8,
            "september": 9, "sep": 9, "sept": 9,
            "october": 10, "oct": 10,
            "november": 11, "nov": 11,
            "december": 12, "dec": 12
        }

        # Check date_str first (e.g. "2025 September")
        if date_str:
            for part in date_str.replace(",", " ").split():
                clean_part = part.strip().lower()
                if clean_part.isdigit() and len(clean_part) == 4:
                    year = int(clean_part)
                elif clean_part in months_map:
                    month = months_map[clean_part]

        # If year not found, look at pub_text
        if not year:
            # Look for 4 digit year between 1980 and 2030
            years_found = re.findall(r'\b(19\d\d|20\d\d)\b', pub_text)
            if years_found:
                year = int(years_found[-1])

        return year, month, date_str.strip() if date_str else None

    def _clean_title(self, raw_text: str) -> Tuple[str, str]:
        """Produce title and normalized title."""
        title = raw_text.strip().strip('"\'')
        norm = re.sub(r'\s+', ' ', title).strip().lower()
        return title, norm

    def _extract_metadata(self, pub_text: str) -> Dict[str, Any]:
        """Extract indexing, impact factor, quartile, publication type from text."""
        meta = {
            "indexing_status": [],
            "impact_factor": None,
            "quartile": None,
            "publication_type": "journal-article",
            "journal_name": None,
            "conference_name": None,
            "issn": None,
        }

        lower_text = pub_text.lower()
        if "scie" in lower_text or "sci" in lower_text:
            meta["indexing_status"].append("SCIE")
        if "scopus" in lower_text:
            meta["indexing_status"].append("Scopus")

        if "conference" in lower_text or "proceedings" in lower_text or "symposium" in lower_text or "workshop" in lower_text:
            meta["publication_type"] = "conference-paper"
        elif "chapter" in lower_text:
            meta["publication_type"] = "book-chapter"

        # Impact factor
        m_if = re.search(r'(?:impact factor|if:?)\s*([\d\.]+)', lower_text)
        if m_if:
            try:
                meta["impact_factor"] = float(m_if.group(1))
            except ValueError:
                pass

        # Quartile
        m_q = re.search(r'\b(q[1-4])\b', lower_text)
        if m_q:
            meta["quartile"] = m_q.group(1).upper()

        # ISSN
        m_issn = re.search(r'\b(?:issn|eissn)[:\s]*([0-9]{4}-[0-9]{3}[0-9xX])\b', pub_text, re.IGNORECASE)
        if m_issn:
            meta["issn"] = m_issn.group(1).upper()

        return meta

    def parse(self) -> List[Dict[str, Any]]:
        """Parses the publications CSV."""
        records = []
        with open(self.file_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    faculty_name = row.get("Faculty Name", "").strip()
                    pub_text = row.get("Publication", "").strip()
                    date_str = row.get("Date", "").strip()
                    
                    if not faculty_name or not pub_text:
                        continue

                    doi, doi_url = self._extract_doi(pub_text)
                    year, month, formatted_date_str = self._extract_year_and_date(date_str, pub_text)
                    title, norm_title = self._clean_title(pub_text)
                    meta = self._extract_metadata(pub_text)

                    record = {
                        "faculty_name_raw": faculty_name,
                        "title": title,
                        "normalized_title": norm_title,
                        "doi": doi,
                        "doi_url": doi_url,
                        "year": year,
                        "month": month,
                        "raw_date_str": formatted_date_str,
                        "publication_type": meta["publication_type"],
                        "journal_name": meta["journal_name"],
                        "conference_name": meta["conference_name"],
                        "issn": meta["issn"],
                        "indexing_status": meta["indexing_status"] if meta["indexing_status"] else None,
                        "impact_factor": meta["impact_factor"],
                        "quartile": meta["quartile"],
                        "source_csv_text": pub_text,
                        "csv_row_hash": self._calculate_hash(row),
                    }
                    records.append(record)
                except Exception as e:
                    logger.error(f"Error parsing publication row: {e}")
        return records


class PublicationImporter:
    """Imports parsed publication records, linking them to FacultyProfile via PublicationAuthor."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _normalize_name_for_match(self, name: str) -> str:
        """Helper to normalize names for resilient matching."""
        n = name.strip()
        n = re.sub(r'^(Dr\.|Dr|Mr\.|Mr|Ms\.|Ms|Prof\.|Prof)\s+', '', n, flags=re.IGNORECASE)
        n = n.replace('.', ' ')
        n = re.sub(r'\s+', ' ', n).strip().lower()
        return n

    async def _build_faculty_lookup(self) -> Tuple[Dict[str, FacultyProfile], List[Tuple[str, FacultyProfile]]]:
        """Pre-fetch all faculty profiles and variants for fast, robust matching."""
        stmt = select(FacultyProfile).options(
            selectinload(FacultyProfile.name_variants)
        )
        res = await self.session.execute(stmt)
        profiles = res.scalars().unique().all()

        exact_map: Dict[str, FacultyProfile] = {}
        token_list: List[Tuple[str, FacultyProfile]] = []

        for p in profiles:
            norm_raw = self._normalize_name_for_match(p.raw_name)
            exact_map[norm_raw] = p
            exact_map[p.normalized_name.lower().strip()] = p
            token_list.append((norm_raw, p))

            for nv in p.name_variants:
                var_norm = self._normalize_name_for_match(nv.name_variant)
                exact_map[var_norm] = p
                token_list.append((var_norm, p))

        return exact_map, token_list

    def _match_faculty(
        self,
        raw_name: str,
        exact_map: Dict[str, FacultyProfile],
        token_list: List[Tuple[str, FacultyProfile]]
    ) -> Optional[FacultyProfile]:
        """Match author name to FacultyProfile."""
        norm = self._normalize_name_for_match(raw_name)
        if norm in exact_map:
            return exact_map[norm]

        tokens = set(norm.split())
        for ref_norm, prof in token_list:
            ref_tokens = set(ref_norm.split())
            if tokens == ref_tokens or tokens.issubset(ref_tokens) or ref_tokens.issubset(tokens):
                return prof
            if len(tokens.intersection(ref_tokens)) >= 2:
                return prof

        return None

    async def run(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Import publications and link them to faculty members."""
        from app.models.publication import Publication, PublicationAuthor, PublicationSource
        from app.models.metrics import FacultyMetricSnapshot
        from datetime import date

        exact_map, token_list = await self._build_faculty_lookup()

        stats = {
            "total_processed": 0,
            "publications_created": 0,
            "publications_reused": 0,
            "author_links_created": 0,
            "author_links_skipped": 0,
            "unmatched_faculty": 0,
            "errors": 0,
        }

        for record in records:
            stats["total_processed"] += 1
            try:
                faculty = self._match_faculty(record["faculty_name_raw"], exact_map, token_list)
                if not faculty:
                    logger.warning(f"Could not match faculty profile for author: '{record['faculty_name_raw']}'")
                    stats["unmatched_faculty"] += 1

                # Find or create Publication
                pub = None
                if record["doi"]:
                    stmt = select(Publication).where(Publication.doi == record["doi"])
                    res = await self.session.execute(stmt)
                    pub = res.scalars().first()

                if not pub:
                    stmt = select(Publication).where(Publication.normalized_title == record["normalized_title"])
                    res = await self.session.execute(stmt)
                    pub = res.scalars().first()

                if pub:
                    stats["publications_reused"] += 1
                else:
                    pub = Publication(
                        title=record["title"],
                        normalized_title=record["normalized_title"],
                        doi=record["doi"],
                        authors_raw=record["faculty_name_raw"],
                        year=record["year"],
                        month=record["month"],
                        publication_type=record["publication_type"],
                        journal_name=record["journal_name"],
                        conference_name=record["conference_name"],
                        issn=record["issn"],
                        indexing_status=record["indexing_status"],
                        impact_factor=record["impact_factor"],
                        quartile=record["quartile"],
                        citation_count=0,
                        verification_status="verified",
                        attribution_confidence=1.0,
                        metadata_confidence=1.0,
                        risk_level="none",
                        source_csv_text=record["source_csv_text"],
                    )
                    self.session.add(pub)
                    await self.session.flush() # assign pub.id
                    stats["publications_created"] += 1

                # Link PublicationAuthor if faculty found
                if faculty:
                    auth_stmt = select(PublicationAuthor).where(
                        PublicationAuthor.publication_id == pub.id,
                        PublicationAuthor.faculty_id == faculty.id
                    )
                    res = await self.session.execute(auth_stmt)
                    existing_link = res.scalars().first()

                    if not existing_link:
                        pub_author = PublicationAuthor(
                            publication_id=pub.id,
                            faculty_id=faculty.id,
                            author_position=1,
                            author_name_raw=record["faculty_name_raw"],
                            attribution_confidence=1.0,
                            attribution_method="csv_verified",
                            is_corresponding=False,
                        )
                        self.session.add(pub_author)
                        stats["author_links_created"] += 1
                    else:
                        stats["author_links_skipped"] += 1

                # Add PublicationSource
                src_stmt = select(PublicationSource).where(
                    PublicationSource.publication_id == pub.id,
                    PublicationSource.source_system == "csv_import"
                )
                res = await self.session.execute(src_stmt)
                existing_src = res.scalars().first()

                if not existing_src:
                    pub_source = PublicationSource(
                        publication_id=pub.id,
                        source_system="csv_import",
                        source_id=record["csv_row_hash"],
                        source_url=record["doi_url"],
                        raw_metadata={
                            "date_raw": record["raw_date_str"],
                            "faculty_name_raw": record["faculty_name_raw"],
                        },
                        discovery_method="csv_bootstrap",
                    )
                    self.session.add(pub_source)

            except Exception as e:
                logger.error(f"Error importing publication '{record.get('title', '')[:40]}': {e}")
                stats["errors"] += 1
                await self.session.rollback()
                continue

        await self.session.commit()

        # Update metric snapshots for all faculty
        today = date.today()
        stmt = select(FacultyProfile).options(
            selectinload(FacultyProfile.publication_links).selectinload(PublicationAuthor.publication)
        )
        res = await self.session.execute(stmt)
        all_profiles = res.scalars().unique().all()

        for prof in all_profiles:
            pubs = [link.publication for link in prof.publication_links if link.publication]
            citations = [p.citation_count or 0 for p in pubs]
            total_pubs = len(pubs)
            total_cits = sum(citations)

            citations.sort(reverse=True)
            h_idx = 0
            for i, c in enumerate(citations):
                if c >= i + 1:
                    h_idx = i + 1
                else:
                    break
            i10_idx = sum(1 for c in citations if c >= 10)

            # Check if metric snapshot exists for today
            m_stmt = select(FacultyMetricSnapshot).where(
                FacultyMetricSnapshot.faculty_id == prof.id,
                FacultyMetricSnapshot.snapshot_date == today
            )
            m_res = await self.session.execute(m_stmt)
            snap = m_res.scalars().first()

            if snap:
                snap.total_publications = total_pubs
                snap.verified_publications = total_pubs
                snap.total_citations = total_cits
                snap.h_index = h_idx
                snap.i10_index = i10_idx
            else:
                new_snap = FacultyMetricSnapshot(
                    faculty_id=prof.id,
                    snapshot_date=today,
                    total_publications=total_pubs,
                    verified_publications=total_pubs,
                    total_citations=total_cits,
                    h_index=h_idx,
                    i10_index=i10_idx,
                )
                self.session.add(new_snap)

        await self.session.commit()
        return stats
