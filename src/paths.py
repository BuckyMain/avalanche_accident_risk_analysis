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