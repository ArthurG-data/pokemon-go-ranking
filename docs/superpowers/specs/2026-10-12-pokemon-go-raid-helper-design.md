# Pokémon GO Raid Helper — design spec and implementation plan

## Context

Guillaume wants a personal desktop web tool to answer, quickly, "what are my best Pokémon for this raid or gym?" in Pokémon GO. Existing sites (GamePress, PokeBattler) are cluttered, English-only, and don't combine browse-by-type, search, and "can I even get this" in one place. The project folder `/home/arthur/projects/pokemon_go_ranking` is empty; this is a greenfield build.

Decisions already made in brainstorming (do not re-litigate):

| Decision | Choice |
|---|---|
| Scope | PvE only: raid attackers + gym defenders. No PvP. |
| Platform | Desktop browser at home. No mobile work. |
| Architecture | Python pipeline → one `data.json` → static HTML/JS page. No server, no framework, no bundler. |
| Ratings | Computed ourselves from the Game Master with standard community formulas, level 40, 15/15/15 IVs. |
| Per-type view | Toggle between "best attackers of type T" and "best counters vs a type-T boss". |
| Defending | Gym defender quality, not type-specific. |
| Filters | Hide Legendary, Mythical (separate toggles), Mega, Shadow, Elite-TM-only movesets. |
| Layout | **B: type-grid landing** (18 cards, top 3 each) → type table → detail page. Sprites everywhere. |
| Detail "How to get it" | Static facts (evolution, candy, sources) **plus** "right now" raids/eggs/research from the LeekDuck community feed. |
| Language | Pokémon, form and move names in **French**. UI labels stay English. Search matches FR and EN. |

Mockups for the chosen layout live in the session scratchpad at `.superpowers/brainstorm/2068018-1791837643/content/` (`layout.html`, `detail-page.html`). They are throwaway wireframes, not code to keep.

## Data sources (all verified reachable on 2026-10-12)

| Source | URL | Used for |
|---|---|---|
| PokeMiners Game Master | `https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/latest.json` (~19 MB) | Pokémon stats, types, moves, elite moves, shadow flag, mega overrides, class, parent species, buddy km, type chart, move stats |
| PokeAPI CSV names | `https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/{pokemon_species_names,pokemon_form_names,move_names}.csv` | French names (`local_language_id` 5), English (9) for matching |
| PokeAPI sprites | `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{id}.png` and `other/official-artwork/{id}.png` | Sprites by dex number (form-specific ids where they exist) |
| ScrapedDuck (LeekDuck feed) | `https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/{raids,eggs,research}.json` | "Right now" availability. English names like `Mega Charizard Y`, `Shadow Mewtwo`, `Alolan Raichu`; no end dates. |

Game Master facts learned from inspection:
- Entries with `data.pokemonSettings`: 2472. Includes duplicates per species (`CHARIZARD`, `CHARIZARD_NORMAL`, `CHARIZARD_COPY_2019`) with identical stats/moves → dedupe on (pokemonId, form-normalized, stats, types, move lists); drop costume/copy forms (form names containing `COPY`, `COSTUME`, `FALL_2019`, etc., plus any form whose stats+types+moves equal the base form).
- `pokemonClass` ∈ {None, LEGENDARY, MYTHIC, ULTRA_BEAST}. Ultra Beasts count as legendary for the filter.
- Shadow availability = presence of `shadow` key. Megas = `tempEvoOverrides[]` with `tempEvoId`, own `stats` and `typeOverride1/2`.
- Moves: `data.moveSettings` with `movementId`, `pokemonType`, `power`, `durationMs`, `energyDelta` (fast moves end in `_FAST`, positive energy; charged negative). `data.combatMove` is PvP, ignore.
- Type chart: 18 `typeEffective` entries, `attackScalar[18]` in canonical type order.
- Evolution: `parentPokemonId` gives the previous stage; candy cost is on the parent's `evolutionBranch[].candyCost`.

## Scoring model (pipeline/scoring.py, pure functions)

Constants: CPM level 40 = 0.7903; IV 15; STAB 1.2; shadow attack ×1.2, defense ×0.8333; effectiveness 1.6 / 0.625 / 0.390625 (from the GM chart, product of the two defender types).

- `attack = (baseAttack + 15) × CPM`, `defense = (baseDefense + 15) × CPM`, `hp = floor((baseStamina + 15) × CPM)`.
- Damage per move hit vs target: `floor(0.5 × power × attack / target_def × stab × eff) + 1`. Target is a fixed reference raid boss with `target_def = 180` and neutral typing unless a boss type is given.
- Fast move: `FDPS = dmg / (durationMs/1000)`, `FEPS = energyDelta / (duration)`. Charged: `CDPS`, `CEPS = -energyDelta / duration`.
- comboDPS (GamePress): `x = (-C_energy × 0.5 + F_energy × 0.5)`, `y = 900 / defense` (incoming DPS model),
  `DPS = (FDPS×CEPS + CDPS×FEPS)/(CEPS+FEPS) + (CDPS−FDPS)/(CEPS+FEPS) × (0.5 − x/hp) × y`.
- `TDO = DPS × hp / y`. `attack_rating = (DPS³ × TDO)^¼` (GamePress "ER").
- Per-type attacker list: charged move type == T. Fast move any type (its own STAB/eff applied). Flag `pure` when fast is also T (shown as a small badge, not a filter).
- Counter score vs boss type T: same formulas with each move's `eff` against T; also ×(boss's attack effectiveness on us is **not** modelled; keep it simple and say so in the UI tooltip).
- Gym defender rating: same DPS math using the Pokémon's **defender** timing (fast move duration + 2000 ms), best moveset by defender DPS, then `defender_rating = sqrt(defDPS × hp × defense / 1000)`. Scale factor tuned once so top defenders land around 60, matching attack_rating's scale. Heuristic; label it so.
- Every moveset carries `elite_tm: true` if either move is in `eliteQuickMove` / `eliteCinematicMove`. Filtering Elite TM re-picks the best remaining moveset per Pokémon (never drops the Pokémon unless it has no legal moveset).

## Pipeline (Python, uv project, `pipeline/`)

```
pipeline/
  fetch.py        download + cache all sources into data/raw/ (skip if fresh < 24h, --force)
  gamemaster.py   parse GM → dataclasses: Species rows (base/regional/shadow/mega), Move, TypeChart; dedupe
  names.py        PokeAPI CSVs → {species_id/form: fr, en}, {move: fr, en}; GM id → PokeAPI id mapping
  scoring.py      pure functions above
  availability.py ScrapedDuck JSON → per-row "right now" entries, matched by EN name incl. Mega/Shadow/regional prefixes
  build.py        orchestrates, writes web/data.json, prints a summary + list of unmatched names (fails loudly on missing move refs)
tests/            pytest; fixtures are small extracts of the real files
web/
  index.html  app.js  style.css  data.json (generated, committed so GitHub Pages works)
```

`web/data.json` shape (one row per form, ~1 000 rows):

```json
{"built": "2026-10-12", "types": [...18 with fr names...],
 "pokemon": [{"id": "CHARIZARD", "dex": 6, "form": null, "name_fr": "Dracaufeu", "name_en": "Charizard",
   "types": ["FIRE","FLYING"], "flags": {"legendary":false,"mythical":false,"mega":false,"shadow":false},
   "stats": {"atk":223,"def":173,"sta":186}, "sprite": ".../6.png", "art": ".../official-artwork/6.png",
   "forms": ["CHARIZARD_SHADOW","CHARIZARD_MEGA_X","CHARIZARD_MEGA_Y"],
   "movesets": [{"fast":"FIRE_SPIN_FAST","charged":"BLAST_BURN","type":"FIRE","elite_tm":true,"pure":true,
                 "dps":19.8,"tdo":520,"rating":47.3, "vs":{"GRASS":61.2,"ICE":60.8,...18}}],
   "defender": {"rating":25,"fast":"AIR_SLASH_FAST","charged":"DRAGON_CLAW"},
   "get": {"evo_line":[{"id":"CHARMANDER","candy":25},{"id":"CHARMELEON","candy":100},{"id":"CHARIZARD"}],
           "buddy_km":3, "has_shadow":true, "megas":["CHARIZARD_MEGA_X","CHARIZARD_MEGA_Y"],
           "sources":["evolve","wild","eggs"], "now":[{"kind":"raid","tier":"Mega","who":"Mega Charizard Y"}]}}],
 "moves": {"BLAST_BURN": {"name_fr":"Rafale Feu","name_en":"Blast Burn","type":"FIRE","power":120,"dur":3500,"energy":-50}}}
```

Rankings are computed in the browser from this file (sort + filter), so filters never need a rebuild.

## Web UI (`web/`, plain HTML/CSS/JS, desktop)

- **Header**: title, tabs `Types | Gym defenders`, search box (matches `name_fr` and `name_en`, instant dropdown with sprite).
- **Filter bar** (always visible, persisted in `localStorage`): Hide Legendary, Hide Mythical, Hide Mega, Hide Shadow, Hide Elite TM moves; `Attackers | Counters` toggle; Top N (10/25/50/all) on table views.
- **Landing**: 18 type cards in a 6-column grid, each with the type colour header and the current top 3 (sprite, FR name, rating). Card click → type table.
- **Type table**: `← All types`, type chip, rank, sprite (purple glow for shadow, mega artwork for mega), FR name + badges (LEG/MYTH/MEGA/SHADOW, ETM on the move), fast (FR), charged (FR), DPS, TDO, Attack (bar + number), Defend (bar + number). Sortable columns. Row click → detail.
- **Gym defenders**: same table shape sorted by defender rating, with defender moveset.
- **Detail page**: large artwork, FR name (EN in grey), dex number, type chips, links to other forms; stats. Left: best movesets (all, ranked, FR move names, ETM badge), rankings (rank among each relevant type list + gym rank), 18-cell counter grid (opacity for resisted). Right: **How to get it** box: evolution line with sprites + candy, buddy km, shadow/mega existence, source tags, "Right now" block from the feed with its fetch date, or "nothing in the current feed".
- Routing by URL hash (`#type/FIRE`, `#p/CHARIZARD`, `#gym`) so back button and bookmarks work.

## Error handling

- `build.py` fails if a Pokémon references an unknown move or a move has missing power/duration; it prints and skips rows with no stats (placeholders), and lists feed names it couldn't match (expected: a few each run; never fatal).
- Missing French name → fall back to English and log it.
- Missing sprite → page shows a neutral placeholder (`onerror`).
- Feed unreachable → build keeps the last cached copy and marks `now` as stale with its date.

## Testing

- `pytest` on: type chart lookups; stat calculation; comboDPS/TDO/ER for ~5 well-known Pokémon vs published GamePress values within ±5 %; GM parsing + dedupe on a fixture of ~20 species (Charizard family, Darmanitan forms, Mewtwo, a mega, a shadow); name mapping incl. regional/mega forms; feed matching for `Mega X`, `Shadow X`, `Alolan X`.
- One Playwright smoke test (`tests/test_web.py`): serve `web/` statically, load landing, assert 18 cards, click Fire, toggle Hide Mega, search "Dracaufeu", open detail, assert the French name and the How-to-get box render.

## Implementation steps (high level, detailed plan to follow via writing-plans)

1. Scaffold uv project, `.gitignore` (`data/raw/`, `.venv/`, `.superpowers/`), README.
2. `fetch.py` + `gamemaster.py` with tests (parse, dedupe, forms, megas, shadows, moves, type chart).
3. `scoring.py` with tests against reference numbers.
4. `names.py` (FR/EN) with tests; `availability.py` with tests.
5. `build.py` → `web/data.json`; summary output.
6. `web/` page: landing → type table → detail → gym tab → search → filters; hash routing.
7. Playwright smoke test; README usage (`uv run python -m pipeline.build`, open `web/index.html`).

## Verification

- `uv run pytest` green.
- `uv run python -m pipeline.build` completes, prints row count (~1 000) and ≤ a handful of unmatched feed names.
- Open `web/index.html`: Fire top 3 includes Reshiram / Blaziken / Chandelure-class Pokémon; "Hide Legendary" removes Reshiram; search `Dracaufeu` finds Charizard; detail shows `Rafale Feu` for Blast Burn and the evolution line Salamèche → Reptincel → Dracaufeu.
- Playwright smoke test green.

## Known gaps (accepted for v1)

- Unreleased Pokémon in the Game Master are not filtered out (no reliable released list). Add later if they clutter rankings.
- Counter score ignores the boss's damage type against us (survivability vs that boss); TDO uses the generic pressure model.
- Feed has no end dates; "Right now" shows what is listed at build time with the build date.
- Defender rating is a heuristic, not a simulation.

## After plan approval (process)

1. Save this spec to `docs/superpowers/specs/2026-10-12-pokemon-go-raid-helper-design.md` and `git init` + commit.
2. Invoke `superpowers:writing-plans` to produce the step-by-step implementation plan, then execute with TDD.
3. Stop the brainstorm companion server (`stop-server.sh` on the scratchpad session dir).
