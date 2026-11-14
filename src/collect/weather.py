"""Collect Open-Meteo archive weather for region centroids."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from src.paths import BULLETIN_START, RAW, STUDY_END

# Local directory for storing cached historical weather data.
WEATHER_DIR = RAW / "weather"

# Open-Meteo API endpoint for historical weather data.
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_point_weather(
    lat: float,
    lon: float,
    start: str = BULLETIN_START,
    end: str = STUDY_END,
    cache_path: Path | None = None,
    force: bool = False,
) -> pd.DataFrame:
    """
    Retrieve historical daily weather data for a geographical location.

    :param lat: Latitude of the geographical location.
    :param lon: Longitude of the geographical location.
    :param start: Start date of the requested period.
    :param end: End date of the requested period.
    :param cache_path: Optional path for storing processed weather data.
    :param force: Ignore the existing cache and retrieve fresh data.
    :return: DataFrame containing daily weather features.
    """

    # Reuse previously downloaded weather data unless a fresh
    # API request is explicitly required.
    if cache_path is not None and cache_path.exists() and not force:
        return pd.read_parquet(cache_path)

    # Configure the API request with geographical coordinates,
    # the requested date range and daily weather variables.
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(
            [
                # Maximum and minimum daily air temperature at 2 m.
                "temperature_2m_max",
                "temperature_2m_min",

                # Total daily precipitation and snowfall.
                "precipitation_sum",
                "snowfall_sum",

                # Maximum daily wind speed at 10 m.
                "windspeed_10m_max",

                # Total daily sunshine duration.
                "sunshine_duration",
            ]
        ),
        # Align daily weather observations with Swiss local dates
        # for merging with avalanche and IMIS datasets.
        "timezone": "Europe/Zurich",
    }

    # Retrieve historical weather data from Open-Meteo API.
    response = requests.get(ARCHIVE_URL, params=params, timeout=60)

    # Raise exception if the HTTP request was unsuccessful.
    response.raise_for_status()

    # Extract daily weather measurements from JSON and convert to pandas DF
    daily = response.json().get("daily") or {}
    df = pd.DataFrame(daily)

    # Return an empty DataFrame if no weather records are available.
    if df.empty:
        return df

    # Standardize the original API variable names to shorter,
    # consistent feature names for downstream processing.
    df = df.rename(
        columns={
            "time": "date",
            "temperature_2m_max": "t_max",
            "temperature_2m_min": "t_min",
            "precipitation_sum": "precip",
            "snowfall_sum": "snowfall",
            "windspeed_10m_max": "wind_max",
            "sunshine_duration": "sunshine_s",
        }
    )
    # Normalize dates for merging with other daily datasets.
    df["date"] = pd.to_datetime(df["date"])

    # Store geographical coordinates alongside corresponding weather measurements.
    df["lat"] = lat
    df["lon"] = lon

    # Store processed weather data in Parquet format if cache path has been provided.
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_path, index=False)
    return df


def fetch_weather_for_regions(
    regions: pd.DataFrame,
    start: str = BULLETIN_START,
    end: str = STUDY_END,
    force: bool = False,
    by_major_region: bool = True,
) -> pd.DataFrame:
    """
     Retrieve historical weather data for avalanche warning regions.

     Weather data can be collected at the major-region or micro-region
     level. Major-region collection reduces the number of API requests
     by assigning shared weather measurements to associated micro-regions.

     :param regions: DataFrame containing region identifiers and centroids.
     :param start: Start date of the requested period.
     :param end: End date of the requested period.
     :param force: Ignore existing caches and retrieve fresh data.
     :param by_major_region: Collect shared weather data per major region.
     :return: DataFrame containing regional daily weather features.
     """

    # ---------------------------------------------------------------
    # Major-region weather collection
    # ---------------------------------------------------------------

    # Collect weather data once per major region to reduce API requests
    # and processing time when detailed micro-region data is not required.
    if by_major_region and "major_region" in regions.columns:

        # Calculate a representative geographical location for each
        # major region using the mean coordinates of its micro-regions.
        reps = (
            regions.groupby("major_region", as_index=False)
            .agg(centroid_lat=("centroid_lat", "mean"), centroid_lon=("centroid_lon", "mean"))
        )

        # Collect individual major-region weather DataFrames.
        major_weather = []
        for _, row in reps.iterrows():

            # Extract the major-region identifier and define its cache path.
            mid = row["major_region"]
            cache = WEATHER_DIR / f"major_{mid}.parquet"
            try:
                # Retrieve weather data for representative location of current major region.
                df = fetch_point_weather(
                    float(row["centroid_lat"]),
                    float(row["centroid_lon"]),
                    start=start,
                    end=end,
                    cache_path=cache,
                    force=force,
                )
            except Exception:
                # Skip failed requests without interrupting remaining weather collection.
                continue

            # Skip regions without available weather measurements.
            if df.empty:
                continue

            # Associate the weather records with the major-region ID.
            df["major_region"] = mid
            major_weather.append(df)

        # Return an empty DataFrame if no weather data was collected.
        if not major_weather:
            return pd.DataFrame()

        # Combine weather measurements from all major regions.
        mw = pd.concat(major_weather, ignore_index=True)

        # Assign major-region weather measurements to all associated
        # micro-regions through their shared major-region identifier.
        #
        # A left join preserves micro-regions even if their corresponding
        # major-region weather measurements are unavailable.
        out = regions[["region_id", "major_region"]].merge(
            mw,
            on="major_region",
            how="left")
        return out

    # ---------------------------------------------------------------
    # Micro-region weather collection
    # ---------------------------------------------------------------

    # Collect weather measurements separately for each micro-region.
    # This provides higher geographical granularity but requires
    # significantly more API requests.
    parts = []
    for _, row in regions.iterrows():

        # Extract the micro-region identifier and define its cache path.
        rid = row["region_id"]
        cache = WEATHER_DIR / f"{rid}.parquet"
        try:
            # Retrieve historical weather data at the region centroid.
            df = fetch_point_weather(
                float(row["centroid_lat"]),
                float(row["centroid_lon"]),
                start=start,
                end=end,
                cache_path=cache,
                force=force,
            )
        except Exception:
            # Skip failed region requests without stopping entire weather collection process
            continue

        # Skip regions without available weather measurements.
        if df.empty:
            continue

        # Associate weather measurements with the micro-region ID.
        df["region_id"] = rid
        parts.append(df)

    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)
