"""Parse the PokeMiners Game Master into plain dataclasses, one row per usable form."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

TYPES = ["BUG", "DARK", "DRAGON", "ELECTRIC", "FAIRY", "FIGHTING", "FIRE", "FLYING", "GHOST", "GRASS",
         "GROUND", "ICE", "NORMAL", "POISON", "PSYCHIC", "ROCK", "STEEL", "WATER"]
# Order of the 18 entries in each typeEffective.attackScalar array (the game's internal type order).
SCALAR_ORDER = ["NORMAL", "FIGHTING", "FLYING", "POISON", "GROUND", "ROCK", "BUG", "GHOST", "STEEL", "FIRE",
                "WATER", "GRASS", "ELECTRIC", "PSYCHIC", "ICE", "DRAGON", "DARK", "FAIRY"]
_TYPE_PREFIX = "POKEMON_TYPE_"
_CLASS_PREFIX = "POKEMON_CLASS_"
_TEMP_PREFIX = "TEMP_EVOLUTION_"
# Costume / event clones that are not gameplay forms.
COSTUME_RE = re.compile(
    r"(COPY|COSTUME|FALL_|WINTER_|WCS|GOTOUR|TSHIRT|GOFEST|WILDAREA|HALLOWEEN|HOLIDAY|FASHION|PARTY"
    r"|ANNIV|FLYING_|KARIYUSHI|DOCTOR|LIBRE|POP_STAR|ROCK_STAR|VS_|ETERNAMAX|^\d{4}$|_\d{4}$|_\d{4}_)"
)
MOVE_KEYS = ("quickMoves", "cinematicMoves", "eliteQuickMove", "eliteCinematicMove")
_MOVE_TEMPLATE_RE = re.compile(r"^V\d{4}_MOVE_(.+)$")


@dataclass(frozen=True)
class Move:
    id: str
    type: str
    power: float
    duration_ms: int
    energy: int

    @property
    def is_fast(self) -> bool:
        return self.id.endswith("_FAST")


@dataclass(frozen=True)
class Evolution:
    species: str
    candy: int


@dataclass
class Pokemon:
    id: str
    species: str
    dex: int
    form: str | None
    types: tuple[str, ...]
    base_atk: int
    base_def: int
    base_sta: int
    pokemon_class: str | None = None      # "LEGENDARY" | "MYTHIC" | "ULTRA_BEAST" | None
    is_shadow: bool = False
    mega: str | None = None               # "MEGA" | "MEGA_X" | "MEGA_Y" | "PRIMAL" | None
    fast_moves: tuple[str, ...] = ()
    charged_moves: tuple[str, ...] = ()
    elite_fast: tuple[str, ...] = ()
    elite_charged: tuple[str, ...] = ()
    parent: str | None = None
    buddy_km: float | None = None
    has_shadow: bool = False
    mega_ids: tuple[str, ...] = ()
    evolutions: tuple[Evolution, ...] = ()

    @property
    def legendary(self) -> bool:
        return self.pokemon_class in ("LEGENDARY", "ULTRA_BEAST")

    @property
    def mythical(self) -> bool:
        return self.pokemon_class == "MYTHIC"

    def all_fast(self) -> tuple[str, ...]:
        return self.fast_moves + tuple(m for m in self.elite_fast if m not in self.fast_moves)

    def all_charged(self) -> tuple[str, ...]:
        return self.charged_moves + tuple(m for m in self.elite_charged if m not in self.charged_moves)

    def is_elite(self, move_id: str) -> bool:
        return move_id in self.elite_fast or move_id in self.elite_charged


@dataclass
class GameMaster:
    pokemon: list[Pokemon]
    moves: dict[str, Move]
    type_chart: dict[str, dict[str, float]] = field(default_factory=dict)

    def by_id(self) -> dict[str, Pokemon]:
        return {p.id: p for p in self.pokemon}


def _strip_type(t: str) -> str:
    return t.removeprefix(_TYPE_PREFIX)


def _form_suffix(species: str, form: str | None) -> str | None:
    """'CHARIZARD_NORMAL' -> None, 'RAICHU_ALOLA' -> 'ALOLA', 'NIDORAN_NORMAL' -> None."""
    if not form:
        return None
    suffix = form.removeprefix(species + "_")
    if suffix == "NORMAL" or suffix.endswith("_NORMAL"):
        return None
    return suffix


def effectiveness(chart: dict[str, dict[str, float]], move_type: str, defender_types) -> float:
    mult = 1.0
    for t in defender_types:
        mult *= chart[move_type][t]
    return mult


def parse(entries: list[dict]) -> GameMaster:
    moves: dict[str, Move] = {}
    chart: dict[str, dict[str, float]] = {}
    raw_rows: list[tuple[int, dict]] = []
    numeric_ids: dict[int, str] = {}   # newer moves use an int movementId; name comes from the templateId
    for e in entries:
        data = e.get("data", {})
        tid = e.get("templateId", "")
        if "moveSettings" in data:
            m = data["moveSettings"]
            move_id = m["movementId"]
            if not isinstance(move_id, str):
                named = _MOVE_TEMPLATE_RE.match(tid)
                if not named:
                    continue   # mega-only signature moves (VM_MOVE_TEMP_EVOLUTION_*) are not in move lists
                numeric_ids[int(move_id)] = move_id = named.group(1)
            if m.get("durationMs") is None:
                continue
            moves[move_id] = Move(
                id=move_id, type=_strip_type(m["pokemonType"]),
                power=float(m.get("power") or 0.0), duration_ms=int(m["durationMs"]),
                energy=int(m.get("energyDelta") or 0),
            )
        elif "typeEffective" in data:
            t = data["typeEffective"]
            chart[_strip_type(t["attackType"])] = dict(zip(SCALAR_ORDER, t["attackScalar"]))
        elif "pokemonSettings" in data and re.match(r"^V\d{4}_", tid):
            raw_rows.append((int(tid[1:5]), data["pokemonSettings"]))

    for _, p in raw_rows:
        for k in MOVE_KEYS:
            if k in p:
                p[k] = [numeric_ids.get(m, m) if isinstance(m, int) else m for m in p[k]]
                p[k] = [m if isinstance(m, str) else f"UNKNOWN_MOVE_{m}" for m in p[k]]
    pokemon = _build_pokemon(raw_rows)
    missing = sorted({m for p in pokemon for m in p.all_fast() + p.all_charged() if m not in moves})
    if missing:
        raise ValueError(f"Pokémon reference moves missing from the Game Master: {', '.join(missing)}")
    return GameMaster(pokemon, moves, chart)


def _build_pokemon(raw_rows: list[tuple[int, dict]]) -> list[Pokemon]:
    groups: dict[tuple, list[tuple[int, str | None, dict]]] = {}
    for dex, p in raw_rows:
        species = p["pokemonId"]
        form = _form_suffix(species, p.get("form"))
        if form and COSTUME_RE.search(form):
            continue
        stats = p.get("stats") or {}
        if not stats.get("baseAttack"):
            continue
        types = tuple(_strip_type(t) for t in (p.get("type"), p.get("type2")) if t)
        key = (species, stats["baseAttack"], stats["baseDefense"], stats["baseStamina"], types,
               tuple(sorted(p.get("quickMoves", []))), tuple(sorted(p.get("cinematicMoves", []))))
        groups.setdefault(key, []).append((dex, form, p))

    out: list[Pokemon] = []
    seen: set[str] = set()
    for key, members in groups.items():
        members.sort(key=lambda m: (m[1] is not None, m[1] or ""))   # literal base row first
        dex, form, p = members[0]
        species, atk, dfn, sta, types = key[0], key[1], key[2], key[3], key[4]
        row_id = species if form is None else f"{species}_{form}"
        if row_id in seen:
            continue   # e.g. DEOXYS vs DEOXYS_NORMAL differ in detail; keep the base template
        seen.add(row_id)
        has_shadow = any("shadow" in m[2] for m in members)
        temp_evos: dict[str, dict] = {}
        for m in members:
            for t in m[2].get("tempEvoOverrides", []):
                if t.get("tempEvoId") and t.get("stats"):
                    temp_evos.setdefault(t["tempEvoId"].removeprefix(_TEMP_PREFIX), t)
        pokemon_class = (p.get("pokemonClass") or "").removeprefix(_CLASS_PREFIX) or None
        evolutions = tuple(Evolution(b["evolution"], int(b.get("candyCost", 0)))
                           for b in p.get("evolutionBranch", []) if b.get("evolution"))
        base = Pokemon(
            id=row_id, species=species, dex=dex, form=form, types=types,
            base_atk=atk, base_def=dfn, base_sta=sta, pokemon_class=pokemon_class,
            fast_moves=tuple(p.get("quickMoves", [])), charged_moves=tuple(p.get("cinematicMoves", [])),
            elite_fast=tuple(p.get("eliteQuickMove", [])), elite_charged=tuple(p.get("eliteCinematicMove", [])),
            parent=p.get("parentPokemonId"), buddy_km=p.get("kmBuddyDistance"),
            has_shadow=has_shadow, mega_ids=tuple(temp_evos), evolutions=evolutions,
        )
        out.append(base)
        if has_shadow:
            out.append(replace(base, id=f"{row_id}_SHADOW", is_shadow=True, has_shadow=False, mega_ids=()))
        for mega, t in temp_evos.items():
            mtypes = tuple(_strip_type(x) for x in (t.get("typeOverride1"), t.get("typeOverride2")) if x) or types
            s = t["stats"]
            out.append(replace(base, id=f"{row_id}_{mega}", types=mtypes, mega=mega,
                               base_atk=s["baseAttack"], base_def=s["baseDefense"], base_sta=s["baseStamina"],
                               has_shadow=False, mega_ids=(), evolutions=()))
    return out


def load(path: Path) -> GameMaster:
    return parse(json.loads(Path(path).read_text(encoding="utf-8")))
