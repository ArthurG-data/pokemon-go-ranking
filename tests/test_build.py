import json
import shutil

import pytest

from pipeline.availability import load_feed, match
from pipeline.build import build, build_data
from pipeline.gamemaster import TYPES
from tests.conftest import FIX, write_feed


@pytest.fixture(scope="module")
def data(gm_fx, names_fx, tmp_path_factory):
    d = tmp_path_factory.mktemp("feed")
    write_feed(d)
    now_by_id, _ = match(gm_fx.pokemon, names_fx.species_en, load_feed(d))
    return build_data(gm_fx, names_fx, now_by_id, built="2026-10-12")


@pytest.fixture(scope="module")
def by(data):
    return {r["id"]: r for r in data["pokemon"]}


def test_top_level_shape(data):
    assert data["built"] == "2026-10-12"
    assert [t["id"] for t in data["types"]] == TYPES
    assert data["types"][6] == {"id": "FIRE", "name_fr": "Feu", "name_en": "Fire"}
    assert data["moves"]["BLAST_BURN"] == {"name_fr": "Rafale Feu", "name_en": "Blast Burn", "type": "FIRE",
                                           "power": 120.0, "dur": 3500, "energy": -50}


def test_charizard_row(by):
    c = by["CHARIZARD"]
    assert c["name_fr"] == "Dracaufeu" and c["name_en"] == "Charizard" and c["types"] == ["FIRE", "FLYING"]
    assert c["flags"] == {"legendary": False, "mythical": False, "mega": False, "shadow": False}
    assert c["stats"] == {"atk": 223, "def": 173, "sta": 186} and c["l40"]["hp"] == 158
    assert c["sprite"].endswith("/pokemon/6.png") and c["art"].endswith("/official-artwork/6.png")
    assert set(c["forms"]) == {"CHARIZARD_SHADOW", "CHARIZARD_MEGA_X", "CHARIZARD_MEGA_Y"}
    best = c["movesets"][0]
    assert best["type"] == "FIRE" and best["rating"] > 0 and set(best["vs"]) == set(TYPES)
    assert best["vs"]["GRASS"] > best["rating"] > best["vs"]["WATER"]
    blast = next(m for m in c["movesets"] if m["fast"] == "FIRE_SPIN_FAST" and m["charged"] == "BLAST_BURN")
    assert blast["elite_tm"] and blast["pure"]
    assert c["movesets"] == sorted(c["movesets"], key=lambda m: -m["rating"])
    assert all(m["rating"] > 0 for m in c["movesets"])
    assert c["defender"]["rating"] > 0 and c["defender"]["fast"] and c["defender_no_elite"]["rating"] > 0
    assert by["CHARIZARD_SHADOW"]["flags"]["shadow"] and by["CHARIZARD_SHADOW"]["movesets"][0]["dps"] > best["dps"]
    assert by["MEWTWO"]["flags"]["legendary"] and by["MEW"]["flags"]["mythical"] and by["KARTANA"]["flags"]["legendary"]


def test_how_to_get(by):
    g = by["CHARIZARD"]["get"]
    assert [(e["id"], e["candy"]) for e in g["evo_line"]] == [("CHARMANDER", 25), ("CHARMELEON", 100), ("CHARIZARD", None)]
    assert g["evo_line"][0]["name_fr"] == "Salamèche" and g["evo_line"][0]["sprite"].endswith("/4.png")
    assert g["buddy_km"] == 3.0 and g["has_shadow"] is True
    assert g["megas"] == ["CHARIZARD_MEGA_X", "CHARIZARD_MEGA_Y"] and g["sources"] == ["evolve"]
    assert by["CHARMANDER"]["get"]["sources"] == ["wild", "eggs"]
    assert by["CHARMANDER"]["get"]["now"] == [{"kind": "egg", "label": "2 km eggs", "who": "Charmander"},
                                              {"kind": "research", "label": "Catch 5 Fire-types", "who": "Charmander"}]
    assert by["CHARIZARD_MEGA_Y"]["get"]["now"] == [{"kind": "raid", "label": "Mega Raids", "who": "Mega Charizard Y"}]
    assert by["CHARIZARD_MEGA_Y"]["get"]["sources"] == ["mega_energy"] and by["CHARIZARD_MEGA_Y"]["get"]["megas"] == []
    assert by["CHARIZARD_SHADOW"]["get"]["sources"] == ["rocket"]
    assert by["CHARIZARD_SHADOW"]["get"]["evo_line"][-1]["id"] == "CHARIZARD_SHADOW"
    assert by["MEWTWO"]["get"]["sources"] == ["raids"] and by["MEW"]["get"]["sources"] == ["research"]
    assert [e["id"] for e in by["RAICHU_ALOLA"]["get"]["evo_line"]] == ["PICHU", "PIKACHU", "RAICHU_ALOLA"]
    assert by["CHARIZARD"]["get"]["now"] == []


def test_ditto_has_no_rankable_moveset(by):
    d = by["DITTO"]
    assert d["name_fr"] == "Métamorph" and d["movesets"] == []
    assert d["defender"] == {"rating": 0, "fast": None, "charged": None}


def test_build_writes_json(tmp_path, capsys):
    raw = tmp_path / "raw"
    shutil.copytree(FIX, raw)
    (raw / "gamemaster.json").write_bytes((FIX / "gm_small.json").read_bytes())
    write_feed(raw)
    out = tmp_path / "web" / "data.json"
    build(raw_dir=raw, out=out, fetch=False)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["pokemon"]) > 20 and data["moves"]
    printed = capsys.readouterr().out
    assert "wrote" in printed and "Nonexistmon" in printed


def test_pokemon_that_cannot_defend_gyms_get_no_defender_rating(by):
    for pid in ("CHARIZARD_MEGA_Y", "KYOGRE_PRIMAL", "MEW"):
        assert by[pid]["defender"] == {"rating": 0, "fast": None, "charged": None}, pid
        assert by[pid]["defender_no_elite"]["rating"] == 0, pid
    assert by["CHARIZARD_SHADOW"]["defender"]["rating"] > 0      # shadows can defend
    assert by["MEWTWO"]["defender"]["rating"] > 0                 # legendaries can defend
