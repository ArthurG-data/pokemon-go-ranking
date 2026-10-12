import json
from pathlib import Path

import pytest

from pipeline.gamemaster import load

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def gm_fx():
    return load(FIX / "gm_small.json")


@pytest.fixture(scope="session")
def names_fx():
    from pipeline.names import load_names
    return load_names(FIX)


def write_feed(d: Path) -> None:
    (d / "raids.json").write_text(json.dumps([
        {"name": "Mega Charizard Y", "tier": "Mega Raids"},
        {"name": "Shadow Mewtwo", "tier": "5-Star Raids"},
        {"name": "Alolan Raichu", "tier": "1-Star Raids"},
        {"name": "Giratina (Altered)", "tier": "5-Star Raids"},
        {"name": "Galarian Darmanitan (Standard)", "tier": "3-Star Raids"},
        {"name": "Nonexistmon", "tier": "1-Star Raids"},
    ]), encoding="utf-8")
    (d / "eggs.json").write_text(json.dumps([{"name": "Charmander", "eggType": "2 km"}]), encoding="utf-8")
    (d / "research.json").write_text(json.dumps([
        {"text": "<span>Catch 5 Fire-types</span>", "rewards": [{"name": "Charmander"}]},
    ]), encoding="utf-8")


@pytest.fixture
def feed_dir(tmp_path):
    write_feed(tmp_path)
    return tmp_path
