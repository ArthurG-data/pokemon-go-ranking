import time
import pytest

from pipeline.fetch import SOURCES, fetch_all, fetch_one


class FakeDownloader:
    def __init__(self, payload=b"data", fail=False):
        self.payload, self.fail, self.calls = payload, fail, 0

    def __call__(self, url):
        self.calls += 1
        if self.fail:
            raise OSError("network down")
        return self.payload


def test_sources_cover_every_file_the_pipeline_reads():
    assert set(SOURCES) == {
        "gamemaster.json", "pokemon_species.csv", "pokemon_species_names.csv", "pokemon.csv",
        "moves.csv", "move_names.csv", "raids.json", "eggs.json", "research.json",
    }


def test_downloads_when_missing(tmp_path):
    dl = FakeDownloader(b"hello")
    path = fetch_one("x.json", "http://example/x", tmp_path, download=dl)
    assert path.read_bytes() == b"hello" and dl.calls == 1


def test_fresh_cache_is_reused(tmp_path):
    dl = FakeDownloader()
    fetch_one("x.json", "http://example/x", tmp_path, download=dl)
    fetch_one("x.json", "http://example/x", tmp_path, download=dl)
    assert dl.calls == 1


def test_stale_cache_is_refreshed(tmp_path):
    dl = FakeDownloader()
    t0 = time.time()
    fetch_one("x.json", "http://example/x", tmp_path, download=dl, now=lambda: t0)
    fetch_one("x.json", "http://example/x", tmp_path, download=dl, now=lambda: t0 + 25 * 3600)
    assert dl.calls == 2


def test_force_refreshes(tmp_path):
    dl = FakeDownloader()
    fetch_one("x.json", "http://example/x", tmp_path, download=dl)
    fetch_one("x.json", "http://example/x", tmp_path, download=dl, force=True)
    assert dl.calls == 2


def test_failure_keeps_cached_copy(tmp_path, capsys):
    fetch_one("x.json", "http://example/x", tmp_path, download=FakeDownloader(b"old"))
    path = fetch_one("x.json", "http://example/x", tmp_path, download=FakeDownloader(fail=True), force=True)
    assert path.read_bytes() == b"old"
    assert "keeping cached copy" in capsys.readouterr().err


def test_failure_without_cache_raises(tmp_path):
    with pytest.raises(RuntimeError, match="x.json"):
        fetch_one("x.json", "http://example/x", tmp_path, download=FakeDownloader(fail=True))


def test_fetch_all_returns_every_path(tmp_path):
    dl = FakeDownloader()
    paths = fetch_all(tmp_path, download=dl)
    assert set(paths) == set(SOURCES) and dl.calls == len(SOURCES)
