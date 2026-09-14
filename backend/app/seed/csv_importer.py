import csv
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
