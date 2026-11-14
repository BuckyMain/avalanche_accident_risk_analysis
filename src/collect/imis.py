"""Collect SLF IMIS snow-station metadata and measurements."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from src.collect.http_utils import get_bytes, get_json
from src.paths import BULLETIN_START, LIVE, RAW, STUDY_END

# SLF IMIS endpoints for station metadata and historical measurements.
STATIONS_URL = "https://measurement-data.slf.ch/imis/stations.csv"
STATIONS_API = "https://measurement-api.slf.ch/public/api/imis/stations"
DAILY_SNOW_URL = (
    "https://measurement-data.slf.ch/imis/data/daily_snow_values/daily_snow.csv"
)

# API endpoints for live weather and snow measurements.
LIVE_MEASUREMENTS_URL = "https://measurement-api.slf.ch/public/api/imis/measurements"
LIVE_DAILY_SNOW_URL = "https://measurement-api.slf.ch/public/api/imis/daily-snow"

# URL template for downloading historical measurements per station.
STATION_HISTORY_TMPL = (
    "https://measurement-data.slf.ch/imis/data/by_station/{code}.csv"
)

# Local cache paths for raw and processed IMIS data.
STATIONS_CACHE = RAW / "imis" / "stations.csv"
DAILY_SNOW_CACHE = RAW / "imis" / "daily_snow.csv"
STATION_DAY_CACHE = RAW / "imis" / "station_day.parquet"

# Storage directory for live IMIS measurements.
LIVE_DIR = LIVE / "imis"


def download_stations(force: bool = False) -> Path:
    """Download and cache IMIS station metadata."""
    get_bytes(STATIONS_URL, cache_path=STATIONS_CACHE, force=force, timeout=60)
    return STATIONS_CACHE


def load_stations(force: bool = False) -> pd.DataFrame:
    """Load IMIS station metadata into a pandas DataFrame."""

    path = download_stations(force=force)
    df = pd.read_csv(path)

    # Explicit column mapping for the expected station metadata schema.
    # The current source column names already match the target names.
    df = df.rename(
        columns={
            "station_code": "station_code",
            "label": "label",
            "lon": "lon",
            "lat": "lat",
            "elevation": "elevation",
            "station_type": "station_type",
            "active": "active",
        }
    )
    return df


def download_daily_snow(force: bool = False) -> Path:
    """Download and cache historical daily snow measurements."""

    # Allow a longer timeout because the historical dataset can be large.
    get_bytes(DAILY_SNOW_URL, cache_path=DAILY_SNOW_CACHE, force=force, timeout=300)
    return DAILY_SNOW_CACHE


def load_daily_snow(
    start: str = BULLETIN_START,
    end: str = STUDY_END,
    force: bool = False,
) -> pd.DataFrame:
    """Load, filter and clean daily snow measurements."""

    path = download_daily_snow(force=force)

    # Parse measurement timestamps when reading the CSV file.
    df = pd.read_csv(path, parse_dates=["measure_date"])

    # Remove timezone information and normalize timestamps to midnight
    # to enable date-based aggregation and merging.
    df["date"] = (
        pd.to_datetime(df["measure_date"])
        .dt.tz_localize(None)
        .dt.normalize())

    # Restrict measurements to the requested study period.
    df = df[
        (df["date"] >= start) & (df["date"] <= end)
    ].copy()

    # Convert snow measurements to numeric values.
    # HS: total snow depth.
    # HN_1D: new snow accumulated over one day.
    df["HS"] = pd.to_numeric(df["HS"], errors="coerce")
    df["HN_1D"] = pd.to_numeric(df["HN_1D"], errors="coerce")

    # Treat negative snow measurement codes as missing values.
    df.loc[df["HS"] < 0, "HS"] = pd.NA
    df.loc[df["HN_1D"] < 0, "HN_1D"] = pd.NA
    return df[["station_code", "date", "HS", "HN_1D"]]


def download_station_history(
        code: str,
        force: bool = False
) -> Path:
    """Download historical measurements for a specific IMIS station."""

    # Construct a station-specific cache path and download URL.
    path = RAW / "imis" / "by_station" / f"{code}.csv"
    url = STATION_HISTORY_TMPL.format(code=code)

    get_bytes(url, cache_path=path, force=force, timeout=180)
    return path


def aggregate_station_day_from_history(
    code: str,
    start: str = BULLETIN_START,
    end: str = STUDY_END,
    force: bool = False,
) -> pd.DataFrame:
    """Aggregate 30-minute station measurements into daily weather features."""

    path = download_station_history(code, force=force)

    # Select only the columns required for daily feature aggregation.
    # TA: air temperature.
    # VW: wind speed.
    # HS: total snow depth.
    usecols = [
        "station_code",
        "measure_date",
        "TA_30MIN_MEAN",
        "VW_30MIN_MEAN",
        "VW_30MIN_MAX",
        "HS",
    ]
    chunks = []

    # Process large historical CSV files in chunks to reduce
    # memory consumption during loading and filtering.
    for chunk in pd.read_csv(
        path,
        usecols=lambda c: c in usecols,
        parse_dates=["measure_date"],
        chunksize=200_000,
    ):
        # Normalize measurement timestamps to calendar dates.
        chunk["date"] = (
            pd.to_datetime(chunk["measure_date"])
            .dt.tz_localize(None)
            .dt.normalize()
        )

        # Remove measurements outside the requested study period.
        chunk = chunk[(chunk["date"] >= start) & (chunk["date"] <= end)]
        # Retain only chunks containing relevant measurements.
        if not chunk.empty:
            chunks.append(chunk)

    # Return an empty DataFrame with the expected schema
    # when no measurements are available.
    if not chunks:
        return pd.DataFrame(
            columns=[
                "station_code",
                "date",
                "ta_mean",
                "ta_max",
                "ta_min",
                "vw_mean",
                "vw_max",
                "hs_mean",
            ]
        )
    # Combine all filtered measurement chunks.
    df = pd.concat(chunks, ignore_index=True)

    # Aggregate historical measurements into one record per station-day.
    agg = (
        df.groupby(["station_code", "date"], as_index=False)
        .agg(
            # Daily mean, maximum and minimum of 30-minute
            # average air temperature measurements.
            ta_mean=("TA_30MIN_MEAN", "mean"),
            ta_max=("TA_30MIN_MEAN", "max"),
            ta_min=("TA_30MIN_MEAN", "min"),

            # Daily average wind speed and maximum recorded wind speed.
            vw_mean=("VW_30MIN_MEAN", "mean"),
            vw_max=("VW_30MIN_MAX", "max"),

            # Daily average snow depth.
            hs_mean=("HS", "mean"),
        )
    )
    return agg


def build_station_day_features(
    station_codes: list[str] | None = None,
    start: str = BULLETIN_START,
    end: str = STUDY_END,
    force: bool = False,
) -> pd.DataFrame:
    """Combine daily snow and weather measurements into station-day features."""

    # Reuse previously processed features unless rebuilding is requested.
    if STATION_DAY_CACHE.exists() and not force:
        return pd.read_parquet(STATION_DAY_CACHE)

    # Load daily snow measurements and standardize feature names.
    snow = load_daily_snow(start=start, end=end, force=force)
    snow = snow.rename(columns={"HS": "hs", "HN_1D": "hn_1d"})

    # Load station metadata for automatic station selection.
    stations = load_stations()

    if station_codes is None:
        # Select active flat-field snow stations (SNOW_FLAT).
        # Prioritize stations at higher elevations and limit the
        # selection to 40 stations to reduce processing time.
        snow_flat = stations[
            (stations["station_type"] == "SNOW_FLAT") & (stations["active"] == True)  # noqa: E712
        ].sort_values("elevation", ascending=False)
        station_codes = snow_flat["station_code"].head(40).tolist()

    # Collect aggregated weather features for the selected stations.
    meteo_parts = []
    for code in station_codes:
        try:
            meteo_parts.append(
                aggregate_station_day_from_history(code, start=start, end=end)
            )
        except Exception:
            # Skip stations that cannot be downloaded or processed
            # without interrupting the entire collection pipeline.
            continue

    # Combine station-level weather features into a single DataFrame.
    # Preserve the required merge columns if no data is available.
    meteo = (
        pd.concat(meteo_parts, ignore_index=True)
        if meteo_parts
        else pd.DataFrame(columns=["station_code", "date"])
    )

    # Merge daily snow and aggregated weather measurements.
    # A left join preserves snow records without matching weather data.
    out = snow.merge(meteo, on=["station_code", "date"], how="left")

    # Sort observations chronologically for each station before
    # calculating rolling snow accumulation.
    out = out.sort_values(["station_code", "date"])

    # Calculate new snow accumulation over the last three observations
    # per station, representing 72 hours when daily records are complete.
    out["hn_3d"] = (
        out.groupby("station_code")["hn_1d"]
        .rolling(3, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )
    # Ensure that the cache directory exists.

    # Store processed features in Parquet format for efficient
    # storage and faster subsequent loading.
    STATION_DAY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(STATION_DAY_CACHE, index=False)
    return out


def download_live_measurements(force: bool = False) -> Path:
    """Download and cache current IMIS weather measurements."""

    # Use the current date to identify the live measurement snapshot.
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    path = LIVE_DIR / f"measurements_{today}.json"

    get_bytes(LIVE_MEASUREMENTS_URL, cache_path=path, force=force, timeout=120)
    return path


def download_live_daily_snow(force: bool = False, period_in_days: int = 7) -> Path:
    """Download recent daily snow measurements for a configurable period."""

    # Generate a date-specific cache path for recent snow measurements.
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    path = LIVE_DIR / f"daily_snow_{today}.json"

    # Request measurements for the specified number of days.
    url = f"{LIVE_DAILY_SNOW_URL}?period_in_days={period_in_days}"
    get_bytes(url, cache_path=path, force=force, timeout=60)
    return path


def load_stations_from_api() -> pd.DataFrame:
    """Retrieve current IMIS station metadata directly from the API."""

    data = get_json(STATIONS_API, timeout=60)
    return pd.DataFrame(data)
