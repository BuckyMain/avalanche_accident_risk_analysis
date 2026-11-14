"""Project paths and shared constants."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
LIVE = DATA / "live"
FIGURES = DATA / "figures"
MODELS = ROOT / "models"
NOTEBOOKS = ROOT / "notebooks"
SRC = ROOT / "src"

# Study window: bulletin archive starts 2021-12-01; accidents available through 2023/24.
BULLETIN_START = "2021-12-01"
STUDY_END = "2024-04-30"

DANGER_MAP = {
    "low": 1,
    "moderate": 2,
    "considerable": 3,
    "high": 4,
    "very_high": 5,
}