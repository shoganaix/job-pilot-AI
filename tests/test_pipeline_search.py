"""Integration tests for the search pipeline with a fake source."""

from pathlib import Path

from jobpilot import storage
from jobpilot.config import (
    Config,
    FamilyConfig,
    ProfileConfig,
    ScoringConfig,
    SearchConfig,
    SearchLocation,
    parse_master_cv,
)
from jobpilot.models import Offer
from jobpilot.pipeline.search import guess_family, plan, run_sync

from ._util import SCAFFOLDS, FakeSource


def _offer(sid, title, company="ACME", location="Madrid"):
    return Offer(source="fake", source_id=sid, title=title, company=company, location=location)


def _config(tmp_path) -> Config:
    return Config(
        profile_path=SCAFFOLDS / "profile.yaml",
        db_path=tmp_path / "db.sqlite",
        snapshot_dir=tmp_path / "snap",
        master_cv=parse_master_cv(SCAFFOLDS / "master_cv.yaml"),
        search=SearchConfig(
            target_offers=50,
            max_results_per_query=20,
            max_pages_per_query=1,
            locations=[SearchLocation(name="Spain", adzuna_country="es")],
        ),
        families=[
            FamilyConfig(id="robotics", label="Robotics", queries=["Robotics Engineer"],
                         sources=["fake"], skills={"ros": 9}),
            FamilyConfig(id="web", label="Web", queries=["Web Developer"],
                         sources=["fake"], skills={}),
        ],
        scoring=ScoringConfig(),
        profile=ProfileConfig(locations=[]),
    )


def test_sync_persists_and_snapshots(tmp_path):
    cfg = _config(tmp_path)
    conn = storage.connect(cfg.db_path)
    source = FakeSource(offers=[
        _offer("1", "Robotics Engineer"),
        _offer("2", "Robotics Engineer (SW)"),
    ])
    run = storage.run_start(conn, "pipeline test")
    stats = run_sync(cfg, conn, {"fake": source}, run=run)

    assert stats.calls["fake"] == 2  # robotics + web, one query each
    assert stats.total_inserted == 2
    assert stats.total_stored == 2
    assert storage.count_offers(conn) == 2

    snap = cfg.snapshot_dir / f"run-{run.id}"
    assert (snap / "fake.jsonl").exists()
    assert (snap / "manifest.json").exists()
    assert (snap / "manifest.json").read_text(encoding="utf-8").find("total_inserted") != -1
    conn.close()


def test_plan_adzuna_uses_country_localized_queries(tmp_path):
    cfg = _config(tmp_path)
    cfg.families[0].adzuna_queries["es"] = ["ingeniero de robótica"]
    cfg.families[0].sources = ["adzuna"]
    cfg.families[1].sources = []  # only robotics to keep the assertion tight
    planned = plan(cfg, {"adzuna": FakeSource(offers=[])})
    assert len(planned) == 1
    assert planned[0].query == "ingeniero de robótica"
    assert planned[0].location.adzuna_country == "es"


def test_plan_adzuna_falls_back_to_english_queries(tmp_path):
    cfg = _config(tmp_path)
    cfg.families[0].sources = ["adzuna"]
    cfg.families[1].sources = []
    planned = plan(cfg, {"adzuna": FakeSource(offers=[])})
    assert [q.query for q in planned] == ["Robotics Engineer"]


def test_sync_dry_run_does_not_persist(tmp_path):
    cfg = _config(tmp_path)
    conn = storage.connect(cfg.db_path)
    source = FakeSource(offers=[_offer("1", "Robotics Engineer")])
    stats = run_sync(cfg, conn, {"fake": source}, run=None, dry_run=True)
    assert storage.count_offers(conn) == 0
    assert stats.total_inserted == 0
    assert not (cfg.snapshot_dir / "run-None").exists()
    conn.close()


def test_sync_skips_disabled_and_several_families(tmp_path):
    cfg = _config(tmp_path)
    conn = storage.connect(cfg.db_path)
    source = FakeSource(offers=[_offer("1", "Robotics Engineer"), _offer("2", "Web Developer")])
    run = storage.run_start(conn)
    stats = run_sync(cfg, conn, {"fake": source}, run=run)
    # both families surface both offers, but the second family only updates them
    assert stats.calls["fake"] == 2
    assert stats.total_inserted == 2
    assert stats.total_updated == 2
    assert stats.stored["fake"] == [2, 2, 0]
    assert stats.total_stored == 2


def test_sync_does_not_store_excluded_seniority(tmp_path):
    cfg = _config(tmp_path)
    cfg.search.exclude_seniority = ["senior", "lead"]
    conn = storage.connect(cfg.db_path)
    source = FakeSource(offers=[
        _offer("1", "Senior Robotics Engineer"),
        _offer("2", "Robotics Engineer"),
    ])
    run = storage.run_start(conn)
    stats = run_sync(cfg, conn, {"fake": source}, run=run)
    assert stats.total_stored == 1
    titles = [o["title"] for o in storage.list_offers(conn)]
    assert titles == ["Robotics Engineer"]
    conn.close()


def test_sync_scroll_feed_fetches_once_and_sieves_all_queries(tmp_path):
    cfg = _config(tmp_path)
    cfg.families[1] = FamilyConfig(id="embedded", label="Embedded", queries=["Embedded Systems"],
                                   sources=["fake"], skills={})
    conn = storage.connect(cfg.db_path)
    source = FakeSource(offers=[
        _offer("1", "Robotics Engineer"),
        _offer("2", "Embedded Systems Engineer"),
        _offer("3", "Barista"),
    ])
    source.scroll_feed = True  # fetch the whole page once, sieve locally
    run = storage.run_start(conn)
    stats = run_sync(cfg, conn, {"fake": source}, run=run)

    assert stats.calls["fake"] == 1  # one fetch, two queries both sieved locally
    assert stats.total_inserted == 2
    assert sorted(o["title"] for o in storage.list_offers(conn)) == [
        "Embedded Systems Engineer", "Robotics Engineer",
    ]
    conn.close()


def test_guess_family_prefers_explicit():
    cfg = _config(Path("."))
    offer = _offer("1", "Robotics Engineer")
    assert guess_family(cfg, offer, "general") == "robotics"
