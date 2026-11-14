"""Collect SLF / EAWS avalanche bulletins (archive + live)."""

# Postpone the evaluation of type annotations
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.collect.http_utils import get_bytes, get_json
from src.paths import LIVE, RAW, BULLETIN_START, STUDY_END, DANGER_MAP

# API endpoints for historical and live avalanche bulletins.
ARCHIVE_TMPL = (
    "https://static.avalanche.report/eaws_bulletins/{d}/{d}-CH.json"
)
LIVE_URL = "https://aws.slf.ch/api/bulletin/caaml/en/json"

# Local storage directories for historical and live bulletin files.
ARCHIVE_DIR = RAW / "bulletin"
LIVE_DIR = LIVE / "bulletin"


def _daterange(start: str, end: str) -> Iterable[date]:
    """Generate all dates within an inclusive date range."""

    # Convert the input strings into date objects.
    s = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()

    # Iterate through the date range one day at a time.
    cur = s
    while cur <= e:
        yield cur
        cur += timedelta(days=1)


def archive_path(day: date | str) -> Path:
    """Return the local archive file path for a specific date."""

    d = day if isinstance(day, str) else day.isoformat()
    return ARCHIVE_DIR / f"{d}-CH.json"


def download_bulletin_day(day: date | str, force: bool = False) -> Path | None:
    """Download and cache the historical bulletin for a specific date."""

    d = day if isinstance(day, str) else day.isoformat()
    path = archive_path(d)

    # Reuse the existing file unless a new download is requested.
    if path.exists() and not force:
        return path

    # Construct the archive URL for the requested date.
    url = ARCHIVE_TMPL.format(d=d)
    try:
        get_bytes(url, cache_path=path, force=force, timeout=30, retries=2)
        return path
    except Exception:
        return None


def download_bulletin_range(
    start: str = BULLETIN_START,
    end: str = STUDY_END,
    force: bool = False,
) -> dict:
    """Download historical bulletins and return download statistics."""

    ok, missing = 0, 0
    for day in _daterange(start, end):

        # Restrict collection to the winter season (October–April)
        # to reduce the amount of downloaded data.
        if day.month not in {10, 11, 12, 1, 2, 3, 4}:
            continue

        # Track successful and failed downloads.
        result = download_bulletin_day(day, force=force)
        if result is None:
            missing += 1
        else:
            ok += 1
    return {"ok": ok, "missing": missing}


def download_live_bulletin(force: bool = False) -> Path:
    """Download the current SLF avalanche bulletin."""

    # Store the live bulletin using the current date as its filename.
    today = date.today().isoformat()
    path = LIVE_DIR / f"{today}-CH.json"
    get_bytes(LIVE_URL, cache_path=path, force=force, timeout=30)
    return path


def _parse_elevation(elev: dict | None) -> tuple[float | None, float | None]:
    """Extract and normalize lower and upper elevation boundaries."""

    # Missing elevation information represents undefined boundaries.
    if not elev:
        return None, None
    lower = elev.get("lowerBound")
    upper = elev.get("upperBound")

    # Convert the lower boundary into a numeric value.
    # Invalid or missing values are represented by None.
    try:
        lower = float(lower) if lower not in (None, "") else None
    except (TypeError, ValueError):
        lower = None

    # Apply the same normalization to the upper boundary.
    try:
        upper = float(upper) if upper not in (None, "") else None
    except (TypeError, ValueError):
        upper = None
    return lower, upper


def parse_bulletin_file(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse one bulletin JSON into region-day and problem tables."""

    # Load the raw bulletin data from the local JSON file.
    data = json.loads(path.read_text(encoding="utf-8"))
    bulletins = data.get("bulletins") or []

    # Store aggregated regional information and individual
    # avalanche problems in separate collections.
    region_rows: list[dict] = []
    problem_rows: list[dict] = []

    # Infer the bulletin date from the filename.
    # Fall back to the bulletin's validity period if necessary.
    stem = path.name.replace("-CH.json", "")
    try:
        bulletin_date = datetime.strptime(stem, "%Y-%m-%d").date()
    except ValueError:
        bulletin_date = None

    # Process each bulletin contained in the JSON file.
    for b in bulletins:
        valid = b.get("validTime") or {}
        start_time = valid.get("startTime")

        # Extract the date from the validity timestamp if the
        # filename does not contain a valid date.
        if bulletin_date is None and start_time:
            bulletin_date = datetime.fromisoformat(
                start_time.replace("Z", "+00:00")
            ).date()

        # Extract the avalanche danger ratings.
        danger_ratings = b.get("dangerRatings") or []

        # Prefer the all-day danger rating.
        # If unavailable, use the first available rating.
        rating = next(
            (r for r in danger_ratings if r.get("validTimePeriod") == "all_day"),
            danger_ratings[0] if danger_ratings else {},
        )

        # Convert the textual danger rating into its numeric level.
        main_value = (rating.get("mainValue") or "").lower()
        danger_level = DANGER_MAP.get(main_value)

        # Extract Switzerland-specific danger level subdivisions.
        subdivision = None
        custom = rating.get("customData") or {}
        if isinstance(custom, dict):
            ch = custom.get("CH") or {}
            subdivision = ch.get("subdivision")

        # Extract all reported avalanche problems.
        problems = b.get("avalancheProblems") or []

        # Collect unique problem types and sort them consistently.
        problem_types = sorted(
            {p.get("problemType") for p in problems if p.get("problemType")}
        )

        # Collect critical slope aspects and elevation boundaries
        # across all avalanche problems in the bulletin.
        all_aspects: set[str] = set()
        elev_lowers: list[float] = []
        elev_uppers: list[float] = []

        for p in problems:

            # Use a set to prevent duplicate slope aspects.
            for a in p.get("aspects") or []:
                all_aspects.add(a)

            # Extract the elevation boundaries of the current problem.
            lo, up = _parse_elevation(p.get("elevation"))
            if lo is not None:
                elev_lowers.append(lo)
            if up is not None:
                elev_uppers.append(up)

        # Aggregate elevation boundaries across avalanche problems.
        critical_elev_min = min(elev_lowers) if elev_lowers else None
        critical_elev_max = max(elev_uppers) if elev_uppers else None

        # Preserve open-ended elevation ranges.
        # Example: above 2400 m has no upper boundary.
        if elev_lowers and not elev_uppers:
            critical_elev_min = min(elev_lowers)
            critical_elev_max = None

        # Example: below 1800 m has no lower boundary.
        if elev_uppers and not elev_lowers:
            critical_elev_max = max(elev_uppers)
            critical_elev_min = None

        # A single bulletin can apply to multiple warning regions.
        # Create a separate record for each affected region.
        for region in b.get("regions") or []:
            region_id = region.get("regionID") or region.get("id")

            # Skip regions without a valid identifier.
            if not region_id:
                continue

            # Create an aggregated regional bulletin record.
            region_rows.append(
                {
                    "date": bulletin_date,
                    "region_id": region_id,
                    "bulletin_id": b.get("bulletinID"),
                    "danger_level": danger_level,
                    "danger_label": main_value,
                    "danger_subdivision": subdivision,
                    "n_problems": len(problem_types),
                    "problem_types": "|".join(problem_types),
                    "critical_aspects": "|".join(sorted(all_aspects)),
                    "critical_elev_min": critical_elev_min,
                    "critical_elev_max": critical_elev_max,
                    "publication_time": b.get("publicationTime"),
                }
            )

            # Create a detailed record for every avalanche problem
            # associated with the current region.
            for p in problems:
                lo, up = _parse_elevation(p.get("elevation"))

                problem_rows.append(
                    {
                        "date": bulletin_date,
                        "region_id": region_id,
                        "bulletin_id": b.get("bulletinID"),
                        "problem_type": p.get("problemType"),
                        "aspects": "|".join(p.get("aspects") or []),
                        "elev_min": lo,
                        "elev_max": up,
                        "valid_time_period": p.get("validTimePeriod"),
                    }
                )

    # Convert the collected records into pandas DataFrames.
    region_df = pd.DataFrame(region_rows)
    problem_df = pd.DataFrame(problem_rows)

    if not region_df.empty:
        # Normalize the date column for filtering and analysis.
        region_df["date"] = pd.to_datetime(region_df["date"])

        # Ensure that the regional table contains only one record
        # per region and date by retaining the first occurrence.
        region_df = region_df.drop_duplicates(subset=["date", "region_id"], keep="first")

    if not problem_df.empty:
        # Normalize dates while retaining individual problem records.
        problem_df["date"] = pd.to_datetime(problem_df["date"])

    return region_df, problem_df


def load_bulletin_tables(
    start: str = BULLETIN_START,
    end: str = STUDY_END,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and combine historical bulletin data for the given date range."""

    # Collect individual DataFrames before concatenating them.
    region_parts: list[pd.DataFrame] = []
    problem_parts: list[pd.DataFrame] = []

    for day in _daterange(start, end):
        # Only process dates within the defined winter season.
        if day.month not in {10, 11, 12, 1, 2, 3, 4}:
            continue
        path = archive_path(day)

        # Skip dates for which no local bulletin file exists.
        if not path.exists():
            continue

        try:
            rdf, pdf = parse_bulletin_file(path)
        except Exception:
            # Skip malformed or unreadable files without
            # interrupting the entire data loading process.
            continue

        # Only collect DataFrames that contain actual records.
        if not rdf.empty:
            region_parts.append(rdf)
        if not pdf.empty:
            problem_parts.append(pdf)

    # Combine all regional bulletin records into a single DataFrame.
    region_df = (
        pd.concat(region_parts, ignore_index=True)
        if region_parts
        else pd.DataFrame()
    )

    # Combine all individual avalanche problem records.
    problem_df = (
        pd.concat(problem_parts, ignore_index=True)
        if problem_parts
        else pd.DataFrame()
    )
    return region_df, problem_df


def load_live_bulletin_json(path: Path | None = None) -> dict:
    """Load the raw JSON data of a live avalanche bulletin."""

    # Download the current bulletin if no local file is provided.
    if path is None:
        path = download_live_bulletin()
    return json.loads(path.read_text(encoding="utf-8"))
