# Pokémon GO Raid Helper

Desktop web page ranking Pokémon GO raid attackers per type and gym defenders, with French names.
Data is computed from the public Game Master by a Python pipeline and written to `web/data.json`.

## Usage

```bash
uv sync
uv run python -m pipeline.build        # downloads sources into data/raw/ (cached 24h), writes web/data.json
python3 -m http.server -d web 8000     # then open http://localhost:8000
```

`uv run python -m pipeline.build --force` re-downloads every source.

## Tests

```bash
uv run pytest                           # pipeline unit tests
uv run playwright install chromium      # once
uv run pytest tests/test_web.py         # browser smoke test (needs web/data.json)
```
