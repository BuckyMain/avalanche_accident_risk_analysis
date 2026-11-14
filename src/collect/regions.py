"""Download EAWS / SLF warning-region geometries."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from src.collect.http_utils import get_bytes
from src.paths import RAW

# EAWS endpoint for Swiss avalanche warning micro-region geometries.
REGIONS_URL = (
    "https://regions.avalanches.org/micro-regions/CH_micro-regions.geojson.json"
)

# Local cache path for the downloaded GeoJSON file.
CACHE = RAW / "regions" / "CH_micro-regions.geojson"


def download_regions(force: bool = False) -> Path:
    """Download and cache Swiss avalanche warning region geometries."""

    # Download the GeoJSON file or reuse the existing cached version.
    get_bytes(REGIONS_URL, cache_path=CACHE, force=force, timeout=60)
    return CACHE


def load_regions(force: bool = False) -> gpd.GeoDataFrame:
    """Load and standardize warning region geometries and spatial attributes."""

    # Retrieve the GeoJSON file and load it into a GeoDataFrame.
    path = download_regions(force=force)
    gdf = gpd.read_file(path)

    # Standardize region identifiers to support different source schemas.
    if "id" in gdf.columns:
        gdf = gdf.rename(columns={"id": "region_id"})
    elif "regionID" in gdf.columns:
        gdf = gdf.rename(columns={"regionID": "region_id"})

    # Ensure consistent identifier types for downstream data merging.
    gdf["region_id"] = gdf["region_id"].astype(str)

    # Extract the major region from the hierarchical Swiss region ID.
    # The first digit after the CH- prefix identifies the major region.
    gdf["major_region"] = gdf["region_id"].str.extract(r"CH-(\d)", expand=False)

    # Standardize the coordinate reference system (CRS) to WGS84.
    # EPSG:4326 represents geographical longitude and latitude.
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)

    # Calculate region centroids using the projected Swiss LV95
    # coordinate reference system (EPSG:2056) to avoid distortions
    # caused by calculating centroids in geographical coordinates.
    #
    # Transform the resulting centroids back to WGS84.
    centroids = gdf.to_crs(2056).geometry.centroid.to_crs(4326)

    # Extract longitude and latitude for each region centroid.
    gdf["centroid_lon"] = centroids.x
    gdf["centroid_lat"] = centroids.y
    return gdf


def regions_table(gdf: gpd.GeoDataFrame | None = None) -> pd.DataFrame:
    """Return a simplified region metadata table without geometries."""

    # Load warning region geometries if no GeoDataFrame is provided.
    if gdf is None:
        gdf = load_regions()

    # Extract region identifiers and centroid coordinates into a
    # standard pandas DataFrame for downstream analysis and merging.
    return pd.DataFrame(
        {
            "region_id": gdf["region_id"],
            "major_region": gdf["major_region"],
            "centroid_lon": gdf["centroid_lon"],
            "centroid_lat": gdf["centroid_lat"],
        }
    )
