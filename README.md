# Pokémon GO Raid Helper

Desktop web page that ranks Pokémon GO **raid attackers per type** and **gym defenders**, with French Pokémon
and move names, filters (legendary, mythical, mega, shadow, Elite TM moves), search, and a "how to get it"
panel with the evolution line and what is currently in raids, eggs and research.

Everything is computed from public data by a Python pipeline and written to one `web/data.json`;
the page is plain HTML/CSS/JS with no server.

## Usage

```bash
uv sync
uv run python -m pipeline.build        # downloads sources into data/raw/ (cached 24h), writes web/data.json
python3 -m http.server -d web 8000     # then open http://localhost:8000
```

`uv run python -m pipeline.build --force` re-downloads every source; `--no-fetch` rebuilds from `data/raw/` offline.

## Data sources

| Source | Used for |
|---|---|
| [PokeMiners Game Master](https://github.com/PokeMiners/game_masters) | stats, moves, forms, type chart |
| [PokeAPI](https://github.com/PokeAPI/pokeapi) CSVs and sprites | French / English names, images |
| [ScrapedDuck](https://github.com/bigfoott/ScrapedDuck) (LeekDuck feed) | current raids, eggs, research |

## How ratings work

Level 40, 15/15/15 IVs. Attacker rating is GamePress-style `(DPS³ × TDO)^¼` from the comboDPS formula against a
reference boss (defense 180, neutral typing); the per-type "counters" score applies type effectiveness of each move.
The gym defender rating is a heuristic: `(HP × defense)^0.75 × (defender DPS)^0.25 / 86`, using the defender's
2 s move delay, so bulk counts three times as much as damage. Megas, Primals and Mythicals get no defender rating
because they cannot be placed in gyms. Unreleased Pokémon in the Game Master are not filtered out.

## Tests

```bash
uv run pytest                           # pipeline unit tests (fixtures in tests/fixtures/)
uv run playwright install chromium      # once
uv run pytest tests/test_web.py         # browser smoke test (needs web/data.json)
uv run python scripts/make_fixtures.py  # regenerate fixtures from data/raw/ after a Game Master change
```
