"""Download and parse SLF/EnviDat avalanche accident records."""

# Postpone the evaluation of type annotations
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

# Import the shared HTTP download utility with caching and retry support
from src.collect.http_utils import get_bytes
from src.paths import RAW

# URL of the historical Swiss avalanche accident dataset
# Provided by SLF (Institute for Snow and Avalanche Research) via EnviDat
ACCIDENTS_URL = (
    "https://www.envidat.ch/dataset/aa035efb-630a-4b7f-a406-f7a579a74de9/"
    "resource/944beac1-11d1-4c84-9bd9-683d12a3c581/download/"
    "version2_avalanche_accidents_all_switzerland_since_1970.csv"
)

# Local cache path for storing the original downloaded CSV file
CACHE = RAW / "accidents" / "avalanche_accidents_since_1970.csv"

# EnviDat CSV has 3 metadata lines, followed by a quoted header line.
# Map the original column names to shorter, standardized snake_case names
# to simplify data processing and analysis.
COLUMN_MAP = {
    # Accident identification and date information
    "avalanche.id": "avalanche_id",
    "date": "date",
    "date.quality": "date_quality",
    "hydrological.year": "hydrological_year",

    # Geographical and administrative information
    "canton": "canton",
    "municipality": "municipality",
    "start.zone.coordinates.latitude": "lat",
    "start.zone.coordinates.longitude": "lon",
    "coordinates.quality": "coordinates_quality",

    # Topographical characteristics of the avalanche start zone
    "start.zone.elevation": "elevation",
    "start.zone.slope.aspect": "aspect",
    "start.zone.inclination": "inclination",

    # Forecasted avalanche danger levels
    "forecasted.dangerlevel.rating1": "danger_level_reported",
    "forecasted.dangerlevel.rating1.subdivision": "danger_subdivision",
    "forecasted.dangerlevel.rating2": "danger_level_reported_2",
    "forecasted.dangerlevel.rating2.subdivision": "danger_subdivision_2",

    # Forecasted critical slope aspects and elevation ranges
    "forecasted.most.dangerous.aspect.and.elevation": "critical_aspect_elevation",

    # Accident consequences and number of affected people
    "number.dead": "n_dead",
    "number.caught": "n_caught",
    "number.fully.buried": "n_buried",

    # Activity performed by the people involved in the accident
    "activity": "activity",
}


def download_accidents(force: bool = False) -> Path:
    """
    Download the historical Swiss avalanche accident dataset from EnviDat.

    Reuse the locally cached CSV file if it already exists, unless
    a fresh download is explicitly requested.

    :param: force: Ignore the existing cache and download fresh data.
    :return: Path to the locally stored CSV file.
    """

    # Download the dataset using the shared HTTP utility.
    get_bytes(ACCIDENTS_URL, cache_path=CACHE, force=force, timeout=120)
    return CACHE


def load_accidents(force: bool = False) -> pd.DataFrame:
    """
    Load, parse and standardize the historical avalanche accident dataset.

    The original EnviDat CSV contains metadata lines and a non-standard
    header format. This function removes the metadata, reconstructs
    the CSV header, standardizes column names and converts relevant
    columns into appropriate data types.

    :param:
        force: Ignore the existing cache and download fresh data.

    :return:
        A pandas DataFrame containing the processed avalanche accident
        records.
    """

    path = download_accidents(force=force)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # Locate the actual CSV header by searching for a line containing both "avalanche.id" and "date".
    # This allows metadata lines to be skipped dynamically instead of
    # relying on a fixed number of metadata lines.
    header_idx = next(
        i for i, line in enumerate(lines) if "avalanche.id" in line and "date" in line
    )

    # Extract the header line and remove surrounding whitespace
    header = lines[header_idx].strip()

    # The original header is stored as a single quoted CSV field.
    # Remove the outer quotation marks and replace escaped double quotes
    # to reconstruct the actual CSV column header.
    if header.startswith('"') and header.endswith('"'):
        header = header[1:-1].replace('""', '"')

    # Reconstruct the CSV content using the corrected header and all
    # subsequent data rows, excluding original metadata lines.
    body = "\n".join([header] + lines[header_idx + 1 :])

    # Convert the reconstructed CSV string into an in-memory text stream and parse into Pandas DF
    df = pd.read_csv(io.StringIO(body))

    # Rename the original columns using the predefined column mapping.
    # Columns not included in COLUMN_MAP retain their original names.
    df = df.rename(columns={c: COLUMN_MAP.get(c, c) for c in df.columns})


    # Convert accident dates into pandas datetime objects.
    # Invalid or unparseable dates are replaced with NaT (Not a Time
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Convert geographical and topographical attributes into numeric values
    for col in ("lat", "lon", "elevation", "inclination", "coordinates_quality"):
        if col in df.columns:
            # Replace invalid or non-numeric values with NaN
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Convert accident consequences and reported avalanche danger levels
    # into numeric values for statistical analysis and machine learning.
    for col in ("n_dead", "n_caught", "n_buried", "danger_level_reported"):
        if col in df.columns:
            # Replace invalid or non-numeric values with NaN
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
