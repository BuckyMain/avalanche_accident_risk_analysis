"""Reusable http module with retry and local caching."""

# Postpone the evaluation of type annotations
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import requests

# Create a shared HTTP session to reuse network connections
# and reduce the overhead of repeated HTTP requests
SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "avalanche-accident-risk-analysis/1.0 (ZHAW Data Analytics student project)"
    }
)


def get_bytes(
    url: str,
    *,
    cache_path: Optional[Path] = None,
    force: bool = False,
    timeout: int = 60,
    retries: int = 3,
    sleep: float = 1.0,
) -> bytes:
    """ Download content from a URL and optionally cache it locally"""

    # Return locally cached data if the file already exists
    # and a new download has not been explicitly requested
    if cache_path is not None and cache_path.exists() and not force:
        return cache_path.read_bytes()

    # Store the most recent exception for debugging purposes
    last_error: Exception | None = None

    # Attempt to download the data up to the specified number of times
    for attempt in range(retries):
        try:
            # Send an HTTP GET request using the shared session
            response = SESSION.get(url, timeout=timeout)

            # Raise an exception if the server returns an HTTP error
            response.raise_for_status()

            data = response.content
            if cache_path is not None:
                # Create missing parent directories if necessary
                cache_path.parent.mkdir(parents=True, exist_ok=True)

                cache_path.write_bytes(data)
            return data
        except Exception as exc:
            last_error = exc
            time.sleep(sleep * (attempt + 1))
    raise RuntimeError(f"Failed to download {url}") from last_error


def get_text(
    url: str,
    *,
    cache_path: Optional[Path] = None,
    force: bool = False,
    timeout: int = 60,
    encoding: str = "utf-8",
) -> str:
    """Download content from a URL and convert it into a text string."""

    # Reuse get_bytes() to handle downloading, caching and retries
    # Decode the raw bytes into a readable string
    # Replace invalid characters instead of raising a decoding error
    return get_bytes(url, cache_path=cache_path, force=force, timeout=timeout).decode(
        encoding, errors="replace"
    )


def get_json(
    url: str,
    *,
    cache_path: Optional[Path] = None,
    force: bool = False,
    timeout: int = 60,
):
    """Download JSON content from a URL and convert it into Python objects."""
    import json

    # Retrieve the raw JSON data using the shared download function
    raw = get_bytes(url, cache_path=cache_path, force=force, timeout=timeout)
    return json.loads(raw)
