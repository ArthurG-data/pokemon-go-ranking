"""Assemble web/data.json from the Game Master, the name tables and the availability feed."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from .availability import Now, load_feed, match
from .fetch import RAW_DIR, fetch_all
from .gamemaster import TYPES, GameMaster, Pokemon, load
from .names import ART_URL, SPRITE_URL, TYPE_NAMES_FR, Names, load_names, move_name, pokemon_name, sprite_id
from .scoring import DEFENDER_DELAY_MS, Stats, combo, defender_rating, level40_stats

OUT = Path("web/data.json")


def _movesets(p: Pokemon, gm: GameMaster, stats: Stats) -> list[dict]:
    out = []
    for f_id in p.all_fast():
        f = gm.moves[f_id]
        for c_id in p.all_charged():
            c = gm.moves[c_id]
            neutral = combo(f, c, stats, p.types)
            if neutral.rating <= 0:
                continue
            vs = {t: round(combo(f, c, stats, p.types, gm.type_chart[f.type][t], gm.type_chart[c.type][t]).rating, 1)
                  for t in TYPES}
            out.append({
                "fast": f_id, "charged": c_id, "type": c.type, "pure": f.type == c.type,
                "elite_tm": p.is_elite(f_id) or p.is_elite(c_id),
                "dps": round(neutral.dps, 1), "tdo": round(neutral.tdo), "rating": round(neutral.rating, 1),
                "vs": vs,
            })
    out.sort(key=lambda m: -m["rating"])
    return out


def can_defend_gym(p: Pokemon) -> bool:
    """Only deployable Pokémon (not Legendary/Mythical/UB per the Game Master) in normal form can be placed.

    Megas/Primals revert before they can be placed, and Shadow Pokémon cannot be placed in gyms.
    """
    return p.deployable and p.mega is None and not p.is_shadow


def _defender(p: Pokemon, gm: GameMaster, stats: Stats, *, allow_elite: bool) -> dict:
    if not can_defend_gym(p):
        return {"rating": 0, "fast": None, "charged": None}
    best: tuple[float, str, str] | None = None
    for f_id in p.all_fast():
        for c_id in p.all_charged():
            if not allow_elite and (p.is_elite(f_id) or p.is_elite(c_id)):
                continue
            s = combo(gm.moves[f_id], gm.moves[c_id], stats, p.types, extra_ms=DEFENDER_DELAY_MS)
            if best is None or s.dps > best[0]:
                best = (s.dps, f_id, c_id)
    if best is None or best[0] <= 0:
        return {"rating": 0, "fast": None, "charged": None}
    return {"rating": round(defender_rating(best[0], stats), 1), "fast": best[1], "charged": best[2]}


def _sources(p: Pokemon) -> list[str]:
    if p.mega:
        return ["mega_energy"]
    if p.is_shadow:
        return ["rocket"]
    if p.mythical:
        return ["research"]
    if p.legendary:
        return ["raids"]
    return ["evolve"] if p.parent else ["wild", "eggs"]


def _child_of(gm: GameMaster) -> dict[str, tuple[str, int]]:
    """Row id -> (parent row id, candy), from evolutionBranch targets (form-aware: Galarian lines stay Galarian)."""
    ids = {p.id for p in gm.pokemon}
    child_of: dict[str, tuple[str, int]] = {}
    for p in gm.pokemon:
        if p.is_shadow or p.mega:
            continue
        for e in p.evolutions:
            target = f"{e.species}_{e.form}" if e.form else e.species
            if target not in ids:
                target = e.species if e.species in ids else None   # e.g. DARMANITAN_STANDARD is the DARMANITAN row
            if target and target != p.id:
                child_of.setdefault(target, (p.id, e.candy))
    return child_of


def _anchor_id(p: Pokemon) -> str:
    """The plain-form row a shadow or mega row belongs to."""
    if p.is_shadow:
        return p.id.removesuffix("_SHADOW")
    if p.mega:
        return p.id.removesuffix("_" + p.mega)
    return p.id


def _evo_line(p: Pokemon, by_id: dict[str, Pokemon], child_of: dict[str, tuple[str, int]],
              base_of: dict[str, Pokemon], names: Names) -> list[dict]:
    chain = [_anchor_id(p)]
    while chain[0] in child_of and child_of[chain[0]][0] not in chain:
        chain.insert(0, child_of[chain[0]][0])
    candies = [child_of[c][1] for c in chain[1:]]
    if len(chain) == 1:   # no branch points here: fall back to walking parentPokemonId by species
        cur = by_id.get(chain[0]) or p
        while cur.parent and cur.parent in base_of and base_of[cur.parent].id not in chain:
            parent = base_of[cur.parent]
            candies.insert(0, next((e.candy for e in parent.evolutions if e.species == cur.species), None))
            chain.insert(0, parent.id)
            cur = parent
    line = []
    for i, rid in enumerate(chain):
        row = p if i == len(chain) - 1 else by_id[rid]
        line.append({"id": row.id, "name_fr": pokemon_name(row, names, "fr"),
                     "sprite": SPRITE_URL.format(sprite_id(row, names)),
                     "candy": candies[i] if i < len(chain) - 1 else None})
    return line


def build_data(gm: GameMaster, names: Names, now_by_id: dict[str, list[Now]], built: str | None = None) -> dict:
    species_rows: dict[str, list[Pokemon]] = {}
    for p in gm.pokemon:
        species_rows.setdefault(p.species, []).append(p)
    base_of: dict[str, Pokemon] = {}
    for p in gm.pokemon:
        if p.form is None and not p.is_shadow and p.mega is None:
            base_of.setdefault(p.species, p)
    for p in gm.pokemon:
        base_of.setdefault(p.species, p)
    by_id = gm.by_id()
    child_of = _child_of(gm)

    rows = []
    for p in gm.pokemon:
        stats = level40_stats(p.base_atk, p.base_def, p.base_sta, shadow=p.is_shadow)
        sid = sprite_id(p, names)
        rows.append({
            "id": p.id, "species": p.species, "dex": p.dex, "form": p.form,
            "name_fr": pokemon_name(p, names, "fr"), "name_en": pokemon_name(p, names, "en"),
            "types": list(p.types),
            "flags": {"legendary": p.legendary, "mythical": p.mythical, "mega": p.mega is not None, "shadow": p.is_shadow},
            "stats": {"atk": p.base_atk, "def": p.base_def, "sta": p.base_sta},
            "l40": {"atk": round(stats.atk), "def": round(stats.dfn), "hp": stats.hp},
            "sprite": SPRITE_URL.format(sid), "art": ART_URL.format(sid),
            "forms": [q.id for q in species_rows[p.species] if q.id != p.id],
            "movesets": _movesets(p, gm, stats),
            "defender": _defender(p, gm, stats, allow_elite=True),
            "defender_no_elite": _defender(p, gm, stats, allow_elite=False),
            "get": {
                "evo_line": _evo_line(p, by_id, child_of, base_of, names),
                "buddy_km": p.buddy_km,
                "has_shadow": p.has_shadow or p.is_shadow,
                "megas": [f"{p.id}_{m}" for m in p.mega_ids],
                "sources": _sources(p),
                "now": [{"kind": n.kind, "label": n.label, "who": n.who} for n in now_by_id.get(p.id, [])],
            },
        })
    moves = {m.id: {"name_fr": move_name(m, names, "fr"), "name_en": move_name(m, names, "en"), "type": m.type,
                    "power": m.power, "dur": m.duration_ms, "energy": m.energy} for m in gm.moves.values()}
    return {
        "built": built or dt.date.today().isoformat(),
        "types": [{"id": t, "name_fr": TYPE_NAMES_FR[t], "name_en": t.title()} for t in TYPES],
        "pokemon": rows,
        "moves": moves,
    }


def build(raw_dir: Path = RAW_DIR, out: Path = OUT, *, fetch: bool = True, force: bool = False) -> dict:
    if fetch:
        fetch_all(raw_dir, force=force)
    gm = load(raw_dir / "gamemaster.json")
    names = load_names(raw_dir)
    now_by_id, unmatched = match(gm.pokemon, names.species_en, load_feed(raw_dir))
    data = build_data(gm, names, now_by_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    rankable = sum(1 for r in data["pokemon"] if r["movesets"])
    print(f"wrote {out}: {len(data['pokemon'])} rows ({rankable} rankable), {len(data['moves'])} moves, "
          f"{out.stat().st_size // 1024} KB")
    if unmatched:
        print("feed names not matched:", ", ".join(sorted(set(unmatched))))
    return data


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Build web/data.json from the public Pokémon GO data sources.")
    ap.add_argument("--force", action="store_true", help="re-download every source even if cached")
    ap.add_argument("--no-fetch", action="store_true", help="use data/raw/ as is, never touch the network")
    args = ap.parse_args(argv)
    build(fetch=not args.no_fetch, force=args.force)


if __name__ == "__main__":
    main()
