import json
from pathlib import Path

import pytest

from pipeline.gamemaster import TYPES, effectiveness, load, parse

FIX = Path(__file__).parent / "fixtures" / "gm_small.json"


@pytest.fixture(scope="module")
def gm():
    return load(FIX)


def test_type_chart_is_complete(gm):
    assert set(gm.type_chart) == set(TYPES) and len(TYPES) == 18
    assert gm.type_chart["FIRE"]["GRASS"] == pytest.approx(1.6)
    assert gm.type_chart["FIRE"]["WATER"] == pytest.approx(0.625)
    assert effectiveness(gm.type_chart, "ELECTRIC", ("GROUND",)) == pytest.approx(0.390625)
    assert effectiveness(gm.type_chart, "FIRE", ("GRASS", "ICE")) == pytest.approx(2.56)


def test_moves_have_defaults_for_null_fields(gm):
    m = gm.moves["BLAST_BURN"]
    assert (m.type, m.power, m.duration_ms, m.energy, m.is_fast) == ("FIRE", 120.0, 3500, -50, False)
    assert gm.moves["FIRE_SPIN_FAST"].is_fast and gm.moves["FIRE_SPIN_FAST"].energy == 9
    assert gm.moves["TRANSFORM_FAST"].power == 0.0  # Game Master has no power for it
    assert gm.moves["STRUGGLE"].energy == 0         # Game Master has no energyDelta for it


def test_charizard_rows_are_deduped_and_expanded(gm):
    ids = [p.id for p in gm.pokemon if p.species == "CHARIZARD"]
    assert ids == ["CHARIZARD", "CHARIZARD_SHADOW", "CHARIZARD_MEGA_X", "CHARIZARD_MEGA_Y"]
    b = gm.by_id()
    base = b["CHARIZARD"]
    assert (base.dex, base.form, base.types) == (6, None, ("FIRE", "FLYING"))
    assert (base.base_atk, base.base_def, base.base_sta) == (223, 173, 186)
    assert "BLAST_BURN" in base.elite_charged and base.is_elite("BLAST_BURN") and not base.is_elite("OVERHEAT")
    assert "BLAST_BURN" in base.all_charged() and "FIRE_SPIN_FAST" in base.all_fast()
    assert base.parent == "CHARMELEON" and base.buddy_km == 3.0
    assert base.has_shadow and base.mega_ids == ("MEGA_X", "MEGA_Y")
    shadow = b["CHARIZARD_SHADOW"]
    assert shadow.is_shadow and shadow.base_atk == 223 and shadow.mega is None and not shadow.has_shadow
    mx = b["CHARIZARD_MEGA_X"]
    assert mx.mega == "MEGA_X" and mx.types == ("FIRE", "DRAGON") and mx.base_atk == 273 and not mx.is_shadow


def test_regional_and_stat_forms_are_kept_costumes_and_clones_dropped(gm):
    ids = {p.id for p in gm.pokemon}
    assert {"RAICHU", "RAICHU_ALOLA", "DARMANITAN", "DARMANITAN_GALARIAN_STANDARD", "DARMANITAN_ZEN",
            "DEOXYS", "DEOXYS_ATTACK", "GIRATINA", "GIRATINA_ORIGIN", "ROTOM_WASH", "LANDORUS_THERIAN"} <= ids
    assert "GIRATINA_ALTERED" not in ids      # identical to base → collapsed into GIRATINA
    assert "LANDORUS_INCARNATE" not in ids
    assert not any("COSTUME" in i or "FALL_2019" in i or "COPY" in i for i in ids)
    assert len([p for p in gm.pokemon if p.id == "DEOXYS"]) == 1  # base and _NORMAL differ but share an id
    assert gm.by_id()["RAICHU_ALOLA"].types == ("ELECTRIC", "PSYCHIC")
    assert gm.by_id()["RAICHU_ALOLA"].parent == "PIKACHU"


def test_classes_and_primal(gm):
    b = gm.by_id()
    assert b["MEWTWO"].pokemon_class == "LEGENDARY" and b["MEWTWO"].legendary and not b["MEWTWO"].mythical
    assert b["MEW"].pokemon_class == "MYTHIC" and b["MEW"].mythical and not b["MEW"].legendary
    assert b["KARTANA"].pokemon_class == "ULTRA_BEAST" and b["KARTANA"].legendary
    assert b["CHARIZARD"].pokemon_class is None
    assert b["KYOGRE_PRIMAL"].mega == "PRIMAL" and b["KYOGRE_PRIMAL"].base_atk == 353


def test_evolutions_carry_candy(gm):
    b = gm.by_id()
    assert [(e.species, e.candy) for e in b["CHARMANDER"].evolutions] == [("CHARMELEON", 25)]
    assert [(e.species, e.candy) for e in b["CHARMELEON"].evolutions] == [("CHARIZARD", 100)]
    assert b["CHARIZARD"].evolutions == ()   # mega branches are not evolutions


def test_missing_move_reference_fails_loudly():
    entries = json.loads(FIX.read_text(encoding="utf-8"))
    entries = [e for e in entries if e.get("data", {}).get("moveSettings", {}).get("movementId") != "BLAST_BURN"]
    with pytest.raises(ValueError, match="BLAST_BURN"):
        parse(entries)


def test_numeric_move_ids_are_resolved_to_names():
    entries = json.loads(FIX.read_text(encoding="utf-8"))
    entries.append({"templateId": "V0497_MOVE_PLASMA_FISTS", "data": {"moveSettings": {
        "movementId": 497, "pokemonType": "POKEMON_TYPE_ELECTRIC", "power": 135.0, "durationMs": 3500,
        "energyDelta": -50}}})
    for e in entries:
        p = e.get("data", {}).get("pokemonSettings")
        if p and p["pokemonId"] == "MEW":
            p["cinematicMoves"] = list(p["cinematicMoves"]) + [497]
    gm = parse(entries)
    assert gm.moves["PLASMA_FISTS"].power == 135.0 and gm.moves["PLASMA_FISTS"].type == "ELECTRIC"
    assert "PLASMA_FISTS" in gm.by_id()["MEW"].charged_moves
    assert all(isinstance(m, str) for p in gm.pokemon for m in p.all_fast() + p.all_charged())
