"""French / English display names and sprite ids from the PokeAPI CSV dumps."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .gamemaster import Move, Pokemon

FR, EN = "5", "9"   # PokeAPI local_language_id
SPRITE_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{}.png"
ART_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{}.png"

TYPE_NAMES_FR = {
    "BUG": "Insecte", "DARK": "Ténèbres", "DRAGON": "Dragon", "ELECTRIC": "Électrik", "FAIRY": "Fée",
    "FIGHTING": "Combat", "FIRE": "Feu", "FLYING": "Vol", "GHOST": "Spectre", "GRASS": "Plante",
    "GROUND": "Sol", "ICE": "Glace", "NORMAL": "Normal", "POISON": "Poison", "PSYCHIC": "Psy",
    "ROCK": "Roche", "STEEL": "Acier", "WATER": "Eau",
}
# region form prefix -> (french suffix, english prefix, PokeAPI identifier part)
REGIONS = {
    "ALOLA": ("d'Alola", "Alolan", "alola"),
    "GALARIAN": ("de Galar", "Galarian", "galar"),
    "HISUIAN": ("de Hisui", "Hisuian", "hisui"),
    "PALDEA": ("de Paldea", "Paldean", "paldea"),
}
MEGA_FR = {"MEGA": "Méga-", "MEGA_X": "Méga-", "MEGA_Y": "Méga-", "PRIMAL": "Primo-"}
MEGA_EN = {"MEGA": "Mega ", "MEGA_X": "Mega ", "MEGA_Y": "Mega ", "PRIMAL": "Primal "}
MEGA_SPRITE = {"MEGA": "mega", "MEGA_X": "mega-x", "MEGA_Y": "mega-y", "PRIMAL": "primal"}
FORM_LABELS = {"A": "Armored"}


@dataclass
class Names:
    species_fr: dict[int, str]
    species_en: dict[int, str]
    species_ident: dict[int, str]
    move_fr: dict[str, str]
    move_en: dict[str, str]
    pokemon_ids: dict[str, int]


def _read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_names(raw_dir: Path) -> Names:
    species_fr: dict[int, str] = {}
    species_en: dict[int, str] = {}
    for r in _read(raw_dir / "pokemon_species_names.csv"):
        table = {FR: species_fr, EN: species_en}.get(r["local_language_id"])
        if table is not None:
            table[int(r["pokemon_species_id"])] = r["name"]
    species_ident = {int(r["id"]): r["identifier"] for r in _read(raw_dir / "pokemon_species.csv")}
    move_ident = {r["id"]: r["identifier"] for r in _read(raw_dir / "moves.csv")}
    move_fr: dict[str, str] = {}
    move_en: dict[str, str] = {}
    for r in _read(raw_dir / "move_names.csv"):
        table = {FR: move_fr, EN: move_en}.get(r["local_language_id"])
        ident = move_ident.get(r["move_id"])
        if table is not None and ident:
            table[ident] = r["name"]
    pokemon_ids = {r["identifier"]: int(r["id"]) for r in _read(raw_dir / "pokemon.csv")}
    return Names(species_fr, species_en, species_ident, move_fr, move_en, pokemon_ids)


def split_form(form: str | None) -> tuple[str | None, str | None]:
    """'GALARIAN_STANDARD' -> ('GALARIAN', 'STANDARD'); 'ORIGIN' -> (None, 'ORIGIN')."""
    if not form:
        return None, None
    head, _, rest = form.partition("_")
    if head in REGIONS:
        return head, rest or None
    return None, form


def _title(s: str, lang: str = "en") -> str:
    if lang == "fr" and s in TYPE_NAMES_FR:
        return TYPE_NAMES_FR[s]
    return FORM_LABELS.get(s) or s.replace("_", " ").title()


def pokemon_name(p: Pokemon, names: Names, lang: str = "fr") -> str:
    table = names.species_fr if lang == "fr" else names.species_en
    name = table.get(p.dex) or _title(p.species)
    region, rest = split_form(p.form)
    xy = f" {p.mega[-1]}" if p.mega in ("MEGA_X", "MEGA_Y") else ""
    if lang == "fr":
        if region:
            name = f"{name} {REGIONS[region][0]}"
        if rest:
            name = f"{name} ({_title(rest, 'fr')})"
        if p.mega:
            name = f"{MEGA_FR[p.mega]}{name}{xy}"
        if p.is_shadow:
            name = f"{name} Obscur"
    else:
        if region:
            name = f"{REGIONS[region][1]} {name}"
        if rest:
            name = f"{name} ({_title(rest)})"
        if p.mega:
            name = f"{MEGA_EN[p.mega]}{name}{xy}"
        if p.is_shadow:
            name = f"Shadow {name}"
    return name


def move_ident(move_id: str) -> str:
    return move_id.removesuffix("_FAST").lower().replace("_", "-")


# GO move ids whose PokeAPI identifier is spelled differently.
MOVE_ALIASES = {"FUTURESIGHT": "future-sight", "SUPER_POWER": "superpower", "PYROBALL": "pyro-ball"}


def move_name(move: Move, names: Names, lang: str = "fr") -> str:
    """Official name; GO variants become 'Base ++' (PLUS) or 'Base (Type)' (WEATHER_BALL_FIRE, TECHNO_BLAST_CHILL)."""
    table = names.move_fr if lang == "fr" else names.move_en
    base_id = move.id.removesuffix("_FAST")
    plus = ""
    for suffix, mark in (("_PLUS_PLUS", " ++"), ("_PLUS", " +")):
        if base_id.endswith(suffix):
            base_id, plus = base_id.removesuffix(suffix), mark
            break
    words = base_id.split("_")
    for cut in range(len(words), 0, -1):
        head = "_".join(words[:cut])
        name = table.get(MOVE_ALIASES.get(head, move_ident(head)))
        if name:
            if cut < len(words):
                type_label = TYPE_NAMES_FR.get(move.type, move.type) if lang == "fr" else move.type.title()
                name = f"{name} ({type_label})"
            return name + plus
    return base_id.replace("_", " ").title() + plus


def sprite_id(p: Pokemon, names: Names) -> int:
    ident = names.species_ident.get(p.dex)
    if ident is None:
        return p.dex
    parts: list[str] = []
    if p.mega:
        parts.append(MEGA_SPRITE[p.mega])
    else:
        region, rest = split_form(p.form)
        if region:
            parts.append(REGIONS[region][2])
        if rest:
            parts.append(rest.lower().replace("_", "-"))
    candidate = "-".join([ident, *parts])
    if candidate in names.pokemon_ids:
        return names.pokemon_ids[candidate]
    for name, pid in names.pokemon_ids.items():
        if name.startswith(candidate + "-"):
            return pid
    tokens = "-".join(parts).split("-")
    for cut in range(len(tokens) - 1, 0, -1):   # 'necrozma-dusk-mane' -> 'necrozma-dusk'
        shorter = "-".join([ident, *tokens[:cut]])
        if shorter in names.pokemon_ids:
            return names.pokemon_ids[shorter]
    return names.pokemon_ids.get(ident, p.dex)
