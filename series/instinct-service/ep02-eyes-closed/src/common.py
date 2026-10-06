"""Shared paths and loaders for the Instinct Service pipeline."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / "series"
MODELS = ROOT / ".models"


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def episode_dir(ep):
    return ROOT / "episodes" / ep


def build_dir(ep):
    d = ROOT / "build" / ep
    d.mkdir(parents=True, exist_ok=True)
    return d


def series_cfg():
    return load(SERIES / "series.json")


def characters():
    return load(SERIES / "characters.json")
