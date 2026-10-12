"""Download and cache every upstream source into data/raw/."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from urllib.request import urlopen

GM_URL = "https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/latest.json"
POKEAPI = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/"
DUCK = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/"

SOURCES: dict[str, str] = {
    "gamemaster.json": GM_URL,
    "pokemon_species.csv": POKEAPI + "pokemon_species.csv",
    "pokemon_species_names.csv": POKEAPI + "pokemon_species_names.csv",
    "pokemon.csv": POKEAPI + "pokemon.csv",
    "moves.csv": POKEAPI + "moves.csv",
    "move_names.csv": POKEAPI + "move_names.csv",
    "raids.json": DUCK + "raids.json",
    "eggs.json": DUCK + "eggs.json",
    "research.json": DUCK + "research.json",
}
RAW_DIR = Path("data/raw")


def _download(url: str) -> bytes:
    with urlopen(url, timeout=120) as resp:
        return resp.read()


def fetch_one(name: str, url: str, raw_dir: Path, *, force: bool = False, max_age_hours: float = 24.0,
              download=_download, now=time.time) -> Path:
    """Return the cached path for `name`, downloading when missing, stale or forced."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / name
    if path.exists() and not force:
        age_hours = (now() - path.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            return path
    try:
        data = download(url)
    except Exception as exc:  # network / HTTP errors
        if path.exists():
            print(f"warning: could not refresh {name} ({exc}); keeping cached copy", file=sys.stderr)
            return path
        raise RuntimeError(f"could not download {name} from {url}: {exc}") from exc
    path.write_bytes(data)
    return path


def fetch_all(raw_dir: Path = RAW_DIR, *, force: bool = False, **kw) -> dict[str, Path]:
    return {name: fetch_one(name, url, raw_dir, force=force, **kw) for name, url in SOURCES.items()}


if __name__ == "__main__":
    for name, path in fetch_all(force="--force" in sys.argv).items():
        print(f"{name}: {path} ({path.stat().st_size // 1024} KB)")
