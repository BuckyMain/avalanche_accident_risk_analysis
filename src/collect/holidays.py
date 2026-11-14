"""Collect Swiss public holidays via OpenHolidays API."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.collect.http_utils import get_json
from src.paths import RAW

# Local directory for storing cached public holiday data.
HOLIDAYS_DIR = RAW / "holidays"

# OpenHolidays API endpoint for retrieving public holidays.
OPENHOLIDAYS_URL = "https://openholidaysapi.org/PublicHolidays"


def download_year(year: int, force: bool = False) -> Path:
    """
    Download and cache Swiss public holidays for a specific year.

    :param year: Calendar year for which holidays are retrieved.
    :param force: Ignore the existing cache and download fresh data.
    :return: Path to the locally stored JSON file.
    """

    # Generate a country- and year-specific cache path.
    path = HOLIDAYS_DIR / f"CH_{year}.json"

    # Reuse the existing cached file unless a fresh download is requested.
    if path.exists() and not force:
        return path

    # Construct the API request for Switzerland and the selected year.
    # Request English holiday names.
    url = (
        f"{OPENHOLIDAYS_URL}?countryIsoCode=CH&languageIsoCode=EN"
        f"&validFrom={year}-01-01&validTo={year}-12-31"
    )
    get_json(url, cache_path=path, force=force, timeout=30)
    return path


def _fallback_swiss_holidays(years: list[int]) -> pd.DataFrame:
    """
    Generate a minimal set of fixed-date Swiss public holidays
    when the OpenHolidays API is unavailable.

    :param years: Calendar years for which holidays are generated.
    :return: DataFrame containing fallback holiday records.
    """

    # Define commonly observed Swiss holidays with fixed calendar dates.
    # This simplified list excludes movable and other regional holidays.
    fixed = [
        (1, 1, "New Year's Day"),
        (1, 2, "Berchtold's Day"),
        (8, 1, "Swiss National Day"),
        (12, 25, "Christmas Day"),
        (12, 26, "St Stephen's Day"),
    ]
    rows = []

    # Generate individual holiday records for each requested year.
    for year in years:
        for month, day, name in fixed:
            rows.append(
                {
                    "date": pd.Timestamp(year=year, month=month, day=day),
                    "name": name,
                    "type": "Public",

                    # Treat fallback holidays as nationwide for simplicity.
                    # Actual holiday coverage may vary by canton.
                    "nationwide": True,
                    "is_holiday": True,
                }
            )
    return pd.DataFrame(rows)


def load_holidays(years: list[int] | None = None, force: bool = False) -> pd.DataFrame:
    """
    Load, parse and standardize Swiss public holiday records.

    Retrieve holiday data from the OpenHolidays API or local cache,
    normalize date values and expand multi-day holidays into individual
    daily records.

    :param years: Calendar years to include in the dataset.
    :param force: Ignore the existing cache and download fresh data.
    :return: DataFrame containing daily public holiday records.
    """

    # Use the predefined study period if no specific years are provided.
    if years is None:
        years = [2021, 2022, 2023, 2024, 2025, 2026, 2027]
    rows = []
    try:
        # Retrieve holiday records for each requested year.
        for year in years:
            # Ensure that the annual holiday data is available locally.
            path = download_year(year, force=force)

            # Load the JSON response from the local cache.
            data = get_json(
                f"{OPENHOLIDAYS_URL}?countryIsoCode=CH&languageIsoCode=EN"
                f"&validFrom={year}-01-01&validTo={year}-12-31",
                cache_path=path,
                force=False,
            )

            # Extract relevant attributes from each holiday record.
            for item in data:
                name = None

                # Prefer the English holiday name from the
                # multilingual API response.
                for n in item.get("name") or []:
                    if n.get("language") == "EN":
                        name = n.get("text")
                        break

                # If no English translation exists, use the first
                # available holiday name.
                if name is None and item.get("name"):
                    name = item["name"][0].get("text")

                # Create a standardized holiday record.
                rows.append(
                    {
                        "date": item.get("startDate"),
                        "end_date": item.get("endDate"),
                        "name": name,
                        "type": item.get("type"),
                        # Indicates whether the holiday applies nationwide.
                        "nationwide": item.get("nationwide"),
                    }
                )
    except Exception:
        # Use the simplified fallback dataset if downloading
        # or processing the API response fails.
        return _fallback_swiss_holidays(years)

    # Convert the collected holiday records into a DataFrame.
    df = pd.DataFrame(rows)

    # Use fallback data if the API returns no holiday records.
    if df.empty:
        return _fallback_swiss_holidays(years)

    # Convert holiday start and end dates into pandas datetime objects.
    df["date"] = pd.to_datetime(df["date"])
    df["end_date"] = pd.to_datetime(df["end_date"])
    expanded = []

    # Expand holidays spanning multiple days into individual daily records.
    # This enables merging with other date-based datasets.
    for _, r in df.iterrows():
        for d in pd.date_range(r["date"], r["end_date"]):
            expanded.append(
                {
                    "date": d,
                    "name": r["name"],
                    "type": r["type"],
                    "nationwide": r["nationwide"],
                    "is_holiday": True,
                }
            )

    # Retain one holiday record per calendar date to prevent
    # duplicate rows when merging with other daily datasets.
    out = pd.DataFrame(expanded).drop_duplicates(subset=["date"])
    return out
