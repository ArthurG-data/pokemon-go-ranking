import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import expect

WEB = Path(__file__).resolve().parents[1] / "web"
pytestmark = pytest.mark.skipif(not (WEB / "data.json").exists(),
                                reason="run `uv run python -m pipeline.build` first")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def site():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(WEB)))
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


def test_landing_type_table_search_and_detail(site, page):
    page.goto(site)
    expect(page.locator(".tcard")).to_have_count(18)
    expect(page.locator(".tcard img.sprite").first).to_be_visible()

    page.locator('.tcard[data-type="FIRE"] .hd').click()
    expect(page).to_have_url(site + "#type/FIRE")
    expect(page.locator("h1")).to_contain_text("Feu")
    assert page.locator("table.rk tbody tr").count() > 5

    page.check("#f-mega")
    expect(page.locator("table.rk .tag.mega")).to_have_count(0)

    page.fill("#search", "Dracaufeu")
    page.locator("#search-results li a").first.click()
    expect(page.locator("h1")).to_contain_text("Dracaufeu")
    expect(page.locator(".howto")).to_contain_text("Salamèche")
    expect(page.locator(".howto")).to_contain_text("Reptincel")
    expect(page.locator(".howto")).to_contain_text("Right now")


def test_elite_filter_repicks_moveset(site, page):
    page.goto(site + "#type/FIRE")
    page.select_option("#topn", "0")
    page.check("#f-mega")
    page.check("#f-shadow")
    row = page.locator("table.rk tbody tr", has_text="Dracaufeu")
    expect(row).to_have_count(1)
    expect(row).to_contain_text("Rafale Feu")          # Blast Burn, an Elite TM move
    page.check("#f-elite")
    row = page.locator("table.rk tbody tr", has_text="Dracaufeu")
    expect(row).to_have_count(1)                        # still ranked …
    expect(row).not_to_contain_text("Rafale Feu")       # … with its next-best moveset


def test_gym_tab_and_no_moveset_pokemon(site, page):
    page.goto(site + "#gym")
    expect(page.locator("h1")).to_contain_text("gym defenders")
    assert page.locator("table.rk tbody tr").count() > 5
    page.goto(site + "#p/DITTO")
    expect(page.locator("h1")).to_contain_text("Métamorph")
    expect(page.locator(".panel").first).to_contain_text("No damaging moveset")
