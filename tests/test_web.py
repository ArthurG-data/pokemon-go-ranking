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


def test_pokemon_that_cannot_defend_show_a_dash(site, page):
    page.goto(site + "#type/FIRE")
    row = page.locator("table.rk tbody tr", has_text="Méga-Dracaufeu Y")
    expect(row.locator("td").last).to_have_text("–")
    page.goto(site + "#gym")
    expect(page.locator(".crumbs")).to_contain_text("bulk weighted 3:1 over damage")


def test_sorting_reorders_the_top_n_instead_of_changing_it(site, page):
    page.goto(site + "#type/FIRE")
    page.select_option("#topn", "10")
    top_before = set(page.locator("table.rk tbody tr td:nth-child(2)").all_inner_texts())
    page.locator('th[data-sort="name"]').click()
    names = page.locator("table.rk tbody tr td:nth-child(2)").all_inner_texts()
    ranks = page.locator("table.rk tbody tr td:nth-child(1)").all_inner_texts()
    assert set(names) == top_before                                  # same 10 Pokémon …
    assert sorted(int(r) for r in ranks) == list(range(1, 11))       # … still numbered by ranking position
    assert ranks != [str(i) for i in range(1, 11)]                   # and the # column moved with them


def test_attackers_of_a_type_are_pokemon_of_that_type(site, page):
    page.goto(site + "#type/WATER")
    page.select_option("#topn", "0")
    names = page.locator("table.rk tbody tr td:nth-child(2)").all_inner_texts()
    assert names and not any("Drattak" in n for n in names)          # Salamence (Dragon/Flying) with Hydrocanon
    page.goto(site + "#type/FIRE")
    names = page.locator("table.rk tbody tr td:nth-child(2)").all_inner_texts()
    assert not any("Mewtwo" in n for n in names)
    page.locator('#mode button[data-mode="counters"]').click()      # counters still include any type
    expect(page.locator("table.rk tbody tr").first).to_be_visible()
    page.goto(site + "#p/SALAMENCE")
    expect(page.locator(".panel").nth(1)).not_to_contain_text("Eau attackers")


def test_counters_show_dps_with_type_effectiveness(site, page):
    def row_dps(type_id, mode):
        page.goto(site + f"#type/{type_id}")
        page.locator(f'#mode button[data-mode="{mode}"]').click()
        page.select_option("#topn", "0")
        row = page.locator("table.rk tbody tr", has_text="Primo-Kyogre").first
        return float(row.locator("td:nth-child(5)").inner_text())
    neutral = row_dps("WATER", "attackers")          # Water moves vs a neutral boss
    vs_fire = row_dps("FIRE", "counters")            # same Water moves vs a Fire boss: super effective
    assert vs_fire == pytest.approx(neutral * 1.6, rel=0.05)
