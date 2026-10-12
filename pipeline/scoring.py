"""Level-40 stats and the community comboDPS / TDO / rating formulas (GamePress style)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import NamedTuple

from .gamemaster import Move

CPM_40 = 0.7903
IV = 15
STAB = 1.2
SHADOW_ATK = 1.2
SHADOW_DEF = 1 / 1.2
TARGET_DEF = 180.0          # reference raid-boss defense the attacker hits
INCOMING = 900.0            # incoming damage pressure; y = INCOMING / defense
DEFENDER_DELAY_MS = 2000    # gym defenders pause 2 s between moves
DEFENDER_SCALE = 86.0       # (hp*def)^0.75 * dps^0.25 / scale ≈ 60 for the best defenders
DEFENDER_BULK_WEIGHT = 0.75 # gym value is mostly how long it survives


@dataclass(frozen=True)
class Stats:
    atk: float
    dfn: float
    hp: int


class MoveScore(NamedTuple):
    dps: float
    eps: float


class ComboScore(NamedTuple):
    dps: float
    tdo: float
    rating: float


def level40_stats(base_atk: int, base_def: int, base_sta: int, *, shadow: bool = False) -> Stats:
    atk = (base_atk + IV) * CPM_40
    dfn = (base_def + IV) * CPM_40
    if shadow:
        atk *= SHADOW_ATK
        dfn *= SHADOW_DEF
    return Stats(atk, dfn, math.floor((base_sta + IV) * CPM_40))


def hit_damage(power: float, atk: float, target_def: float, multiplier: float) -> int:
    return math.floor(0.5 * power * atk / target_def * multiplier) + 1


def move_score(move: Move, stats: Stats, mover_types, eff: float = 1.0, *,
               target_def: float = TARGET_DEF, extra_ms: int = 0) -> MoveScore:
    mult = eff * (STAB if move.type in mover_types else 1.0)
    dmg = hit_damage(move.power, stats.atk, target_def, mult) if move.power > 0 else 0
    secs = (move.duration_ms + extra_ms) / 1000
    return MoveScore(dmg / secs, abs(move.energy) / secs)


def rating(dps: float, tdo: float) -> float:
    return (dps ** 3 * tdo) ** 0.25 if dps > 0 and tdo > 0 else 0.0


def combo(fast: Move, charged: Move, stats: Stats, mover_types, eff_fast: float = 1.0, eff_charged: float = 1.0,
          *, target_def: float = TARGET_DEF, extra_ms: int = 0) -> ComboScore:
    f = move_score(fast, stats, mover_types, eff_fast, target_def=target_def, extra_ms=extra_ms)
    c = move_score(charged, stats, mover_types, eff_charged, target_def=target_def, extra_ms=extra_ms)
    if charged.energy >= 0 or fast.energy <= 0 or f.eps + c.eps <= 0 or (f.dps == 0 and c.dps == 0):
        return ComboScore(0.0, 0.0, 0.0)
    y = INCOMING / stats.dfn
    x = -charged.energy * 0.5 + fast.energy * 0.5
    dps = (f.dps * c.eps + c.dps * f.eps) / (c.eps + f.eps) \
        + (c.dps - f.dps) / (c.eps + f.eps) * (0.5 - x / stats.hp) * y
    dps = max(dps, 0.0)
    tdo = dps * stats.hp / y
    return ComboScore(dps, tdo, rating(dps, tdo))


def defender_rating(def_dps: float, stats: Stats) -> float:
    """Heuristic gym value: bulk (hp × defense) weighted 3:1 over the damage it deals back."""
    if def_dps <= 0:
        return 0.0
    w = DEFENDER_BULK_WEIGHT
    return (stats.hp * stats.dfn) ** w * def_dps ** (1 - w) / DEFENDER_SCALE
