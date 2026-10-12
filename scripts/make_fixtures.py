"""Extract small test fixtures from the real downloaded sources.

Run once after `uv run python -m pipeline.fetch`:  uv run python scripts/make_fixtures.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

RAW = Path("data/raw")
OUT = Path("tests/fixtures")
SPECIES = [
    "CHARMANDER", "CHARMELEON", "CHARIZARD", "PICHU", "PIKACHU", "RAICHU", "DARUMAKA", "DARMANITAN",
    "MEWTWO", "DEOXYS", "HAPPINY", "CHANSEY", "BLISSEY", "DITTO", "LANDORUS", "GIRATINA", "KYOGRE",
    "KARTANA", "MEW", "ROTOM", "LUGIA",
]
MOVE_KEYS = ("quickMoves", "cinematicMoves", "eliteQuickMove", "eliteCinematicMove")


def subset_csv(name: str, keep) -> None:
    with open(RAW / name, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(r for r in rows if keep(r))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    gm = json.loads((RAW / "gamemaster.json").read_text(encoding="utf-8"))
    keep, move_ids, dex = [], set(), set()
    for e in gm:
        data = e.get("data", {})
        if "typeEffective" in data:
            keep.append(e)
        elif "pokemonSettings" in data and data["pokemonSettings"]["pokemonId"] in SPECIES:
            keep.append(e)
            dex.add(int(e["templateId"][1:5]))
            for k in MOVE_KEYS:
                move_ids.update(data["pokemonSettings"].get(k, []))
    for e in gm:
        m = e.get("data", {}).get("moveSettings")
        if m and m["movementId"] in move_ids:
            keep.append(e)
    (OUT / "gm_small.json").write_text(json.dumps(keep), encoding="utf-8")

    idents = {m.removesuffix("_FAST").lower().replace("_", "-") for m in move_ids}
    subset_csv("pokemon_species.csv", lambda r: int(r["id"]) in dex)
    subset_csv("pokemon_species_names.csv",
               lambda r: int(r["pokemon_species_id"]) in dex and r["local_language_id"] in ("5", "9"))
    subset_csv("pokemon.csv", lambda r: int(r["species_id"]) in dex)
    with open(RAW / "moves.csv", newline="", encoding="utf-8") as f:
        pokeapi_move_ids = {r["id"] for r in csv.DictReader(f) if r["identifier"] in idents}
    subset_csv("moves.csv", lambda r: r["id"] in pokeapi_move_ids)
    subset_csv("move_names.csv", lambda r: r["move_id"] in pokeapi_move_ids and r["local_language_id"] in ("5", "9"))
    print("fixtures written:", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
