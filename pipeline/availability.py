"""'Right now' availability (raids, eggs, research) from the ScrapedDuck LeekDuck feed."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .gamemaster import Pokemon
from .names import split_form

REGION_WORDS = {"Alolan": "ALOLA", "Galarian": "GALARIAN", "Hisuian": "HISUIAN", "Paldean": "PALDEA"}
_TAG_RE = re.compile(r"<[^>]+>")
_NOTE_RE = re.compile(r"^(.*?)\s*\((.*)\)\s*$")
_PUNCT_RE = re.compile(r"[^\w\s]")
_PATTERN_NO_RE = re.compile(r"\s+\d+$")   # "Spinda 4" -> "Spinda"


def _norm(name: str) -> str:
    return _PATTERN_NO_RE.sub("", _PUNCT_RE.sub("", name)).strip().lower()


@dataclass(frozen=True)
class FeedName:
    species: str
    shadow: bool = False
    mega: str | None = None
    region: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class Now:
    kind: str    # "raid" | "egg" | "research"
    label: str   # tier, egg distance, or research task text
    who: str     # the feed's own name, for display and for the unmatched report


def parse_feed_name(name: str) -> FeedName:
    note = None
    m = _NOTE_RE.match(name.strip())
    if m:
        name, note = m.group(1), m.group(2)
    words = name.split()
    shadow, mega, region = False, None, None
    while words:
        w = words[0]
        if w == "Shadow":
            shadow = True
        elif w == "Mega":
            mega = "MEGA"
        elif w == "Primal":
            mega = "PRIMAL"
        elif w in REGION_WORDS:
            region = REGION_WORDS[w]
        else:
            break
        words.pop(0)
    if mega == "MEGA" and len(words) > 1 and words[-1] in ("X", "Y"):
        mega = "MEGA_" + words.pop()
    return FeedName(" ".join(words), shadow, mega, region, note)


def load_feed(raw_dir: Path) -> list[tuple[FeedName, Now]]:
    def read(name: str) -> list:
        return json.loads((raw_dir / name).read_text(encoding="utf-8"))

    out: list[tuple[FeedName, Now]] = []
    for r in read("raids.json"):
        out.append((parse_feed_name(r["name"]), Now("raid", r.get("tier", "Raid"), r["name"])))
    for r in read("eggs.json"):
        out.append((parse_feed_name(r["name"]), Now("egg", f"{r.get('eggType', '?')} eggs", r["name"])))
    for task in read("research.json"):
        label = _TAG_RE.sub("", task.get("text", "")).strip()
        for reward in task.get("rewards", []):
            if reward.get("name"):
                out.append((parse_feed_name(reward["name"]), Now("research", label, reward["name"])))
    return out


def _row_key(p: Pokemon, species_en: dict[int, str]) -> tuple:
    region, _ = split_form(p.form)
    return (_norm(species_en.get(p.dex, p.species)), p.is_shadow, p.mega, region)


def match(pokemon: list[Pokemon], species_en: dict[int, str],
          feed: list[tuple[FeedName, Now]]) -> tuple[dict[str, list[Now]], list[str]]:
    index: dict[tuple, list[Pokemon]] = {}
    for p in pokemon:
        index.setdefault(_row_key(p, species_en), []).append(p)

    now_by_id: dict[str, list[Now]] = {}
    unmatched: list[str] = []
    for fname, now in feed:
        rows = index.get((_norm(fname.species), fname.shadow, fname.mega, fname.region), [])
        plain = [r for r in rows if split_form(r.form)[1] is None]
        if fname.note:
            tag = set(fname.note.upper().replace("-", " ").split())
            rows = [r for r in rows if r.form and tag <= set(r.form.split("_"))] or plain
        else:
            rows = plain or rows
        if not rows:
            unmatched.append(now.who)
            continue
        for r in rows:
            entries = now_by_id.setdefault(r.id, [])
            if now not in entries:
                entries.append(now)
    return now_by_id, unmatched
