"""Tests for the SQLite persistence layer."""

from jobpilot import storage
from jobpilot.models import AppStatus, DimensionScore, Offer, Score, Triage

from ._util import temp_db_path


def test_upsert_dedupe_and_update(tmp_path):
    conn = storage.connect(temp_db_path(tmp_path))
    run = storage.run_start(conn, "test")
    offers = [
        Offer(source="adzuna", source_id="a1", title="Robotics Engineer",
              company="ACME", location="Madrid", family="robotics"),
        Offer(source="adzuna", source_id="a2", title="Frontend Dev",
              company="ACME", location="Madrid", family="general"),
        Offer(source="remoteok", source_id="r1", title="Robotics Engineer",
              company="ACME", location="Madrid"),  # dup fingerprint of a1
    ]
    res = storage.upsert_offers(conn, run.id, offers)
    assert res["adzuna"] == [2, 0, 0]
    assert res["remoteok"] == [0, 0, 1]  # r1 is a duplicate fingerprint of a1
    # update existing same (source, source_id)
    offers[0].title = "Robotics Engineer (ROS2)"
    res = storage.upsert_offers(conn, run.id, [offers[0]])
    assert res["adzuna"] == [0, 1, 0]
    assert storage.count_offers(conn) == 2

    fam = storage.list_offers(conn, families=["robotics"])
    assert len(fam) == 1 and fam[0]["title"].startswith("Robotics")
    conn.close()


def test_relaxed_dedupe_by_url(tmp_path):
    conn = storage.connect(temp_db_path(tmp_path))
    run = storage.run_start(conn, "test")
    storage.upsert_offers(conn, run.id, [
        Offer(source="greenhouse", source_id="g1", title="Robotics Engineer",
              company="Acme", location="Remote", apply_url="https://acme.dev/jobs/1"),
    ])
    res = storage.upsert_offers(conn, run.id, [
        Offer(source="lever", source_id="l1", title="Robotics Engineer",
              company="Acme", location="Berlin", apply_url="https://acme.dev/jobs/1"),
    ], relaxed=True)
    assert res["lever"] == [0, 0, 1]
    assert storage.count_offers(conn) == 1
    row = storage.list_offers(conn)[0]
    assert row["location"] == "Berlin"  # old row mutated, not duplicated
    assert row["source"] == "greenhouse"  # original identity kept
    conn.close()


def test_relaxed_dedupe_by_title_company_ignoring_location(tmp_path):
    conn = storage.connect(temp_db_path(tmp_path))
    run = storage.run_start(conn, "test")
    storage.upsert_offers(conn, run.id, [
        Offer(source="hn_hiring", source_id="h1", title="Robotics Engineer",
              company="Acme Robotics", location="Remote (Global)"),
    ])
    res = storage.upsert_offers(conn, run.id, [
        Offer(source="devglobaljobs", source_id="d1", title="Robotics Engineer ",
              company="ACME ROBOTICS", location="San Francisco"),
    ], relaxed=True)
    assert res["devglobaljobs"] == [0, 0, 1]
    assert storage.count_offers(conn) == 1
    conn.close()


def test_relaxed_dedupe_off_by_default(tmp_path):
    conn = storage.connect(temp_db_path(tmp_path))
    run = storage.run_start(conn, "test")
    storage.upsert_offers(conn, run.id, [
        Offer(source="greenhouse", source_id="g1", title="Robotics Engineer",
              company="Acme", location="Remote", apply_url="https://acme.dev/jobs/1"),
    ])
    res = storage.upsert_offers(conn, run.id, [
        Offer(source="lever", source_id="l1", title="Robotics Engineer",
              company="Acme", location="Berlin", apply_url="https://acme.dev/jobs/1"),
    ])
    assert res["lever"] == [1, 0, 0]  # inserted: no relaxed match without the flag
    assert storage.count_offers(conn) == 2
    conn.close()


def test_relaxed_dedupe_two_new_offers_same_company_not_merged(tmp_path):
    conn = storage.connect(temp_db_path(tmp_path))
    run = storage.run_start(conn, "test")
    res = storage.upsert_offers(conn, run.id, [
        Offer(source="hn_hiring", source_id="h1", title="Robotics Engineer",
              company="Acme", location="Remote"),
        Offer(source="hn_hiring", source_id="h2", title="Embedded Engineer",
              company="Acme", location="Remote"),
    ], relaxed=True)
    assert res["hn_hiring"] == [2, 0, 0]
    assert storage.count_offers(conn) == 2
    conn.close()


def test_application_queue(tmp_path):
    conn = storage.connect(temp_db_path(tmp_path))
    run = storage.run_start(conn)
    offer = Offer(source="adzuna", source_id="a1", title="Robotics", company="ACME",
                  location="Madrid", apply_url="https://apply/1", family="robotics")
    storage.upsert_offers(conn, run.id, [offer])
    oid = storage.list_offers(conn)[0]["id"]

    storage.set_application(conn, oid, AppStatus.APPLY, notes="strength: ROS")
    rows = storage.list_applications(conn, statuses=[AppStatus.APPLY])
    assert len(rows) == 1
    assert rows[0]["status"] == "apply"
    assert rows[0]["notes"] == "strength: ROS"
    assert rows[0]["created_at"] and rows[0]["applied_on"] == ""

    storage.set_application(conn, oid, AppStatus.APPLIED)
    rows = storage.list_applications(conn, statuses=[AppStatus.APPLY])
    assert rows == []
    applied = storage.get_application(conn, oid)
    assert applied["applied_on"]  # stamped automatically on apply
    first_created = applied["created_at"]
    assert first_created

    # applied_on and created_at are preserved across later transitions
    storage.set_application(conn, oid, AppStatus.REJECTED)
    later = storage.get_application(conn, oid)
    assert later["applied_on"] == applied["applied_on"]
    assert later["created_at"] == first_created
    conn.close()


def test_connect_migrates_old_applications_schema(tmp_path):
    import sqlite3

    db = temp_db_path(tmp_path)
    raw = sqlite3.connect(db)
    raw.executescript(
        "CREATE TABLE applications ("
        "  offer_id INTEGER PRIMARY KEY, status TEXT NOT NULL DEFAULT 'new',"
        "  cv_variant TEXT NOT NULL DEFAULT '', cv_file TEXT NOT NULL DEFAULT '',"
        "  notes TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',"
        "  updated_at TEXT NOT NULL);"
        "INSERT INTO applications (offer_id, updated_at) VALUES (99, '2026-01-01T00:00:00+00:00');"
    )
    raw.commit()
    raw.close()

    conn = storage.connect(db)  # migration must add created_at/applied_on
    row = storage.get_application(conn, 99)
    assert row["created_at"] == "" and row["applied_on"] == ""
    conn.close()


def test_search_offers(tmp_path):
    conn = storage.connect(temp_db_path(tmp_path))
    run = storage.run_start(conn)
    offers = [
        Offer(source="adzuna", source_id="a1", title="Senior Robotics Engineer",
              company="ACME", location="Madrid", family="robotics",
              description="ROS2 and SLAM for ground vehicles."),
        Offer(source="adzuna", source_id="a2", title="Frontend Dev",
              company="ACME", location="Madrid"),
        Offer(source="adzuna", source_id="a3", title="Robotics Intern",
              company="Beta", location="Remote", family="robotics"),
    ]
    storage.upsert_offers(conn, run.id, offers)
    assert len(storage.search_offers(conn, "robotics")) == 2  # title + family match
    assert len(storage.search_offers(conn, "slam")) == 1  # description match
    assert len(storage.search_offers(conn, "acme")) == 2  # company match
    assert len(storage.search_offers(conn, "robotics madrid")) == 1  # AND across terms
    assert storage.search_offers(conn, "zzz") == []
    assert storage.search_offers(conn, "   ") == []
    conn.close()


def test_scores_roundtrip(tmp_path):
    conn = storage.connect(temp_db_path(tmp_path))
    run = storage.run_start(conn)
    offer = Offer(source="himalayas", source_id="h1", title="GNC Engineer",
                  company="SpaceCo", location="Remote", family="systems_gnc")
    storage.upsert_offers(conn, run.id, [offer])
    oid = storage.list_offers(conn)[0]["id"]

    score = Score(
        offer_id=oid,
        run_id=run.id,
        total=72.5,
        triage=Triage.APPLY,
        breakdown={"skills": DimensionScore(80, 30, "ros2 matched")},
        extracted={"skills": ["ros2", "python"]},
        hard_filters=[],
        reason="good fit",
    )
    storage.save_scores(conn, run.id, [score])
    rows = storage.scores_for_run(conn, run.id)
    assert len(rows) == 1
    assert rows[0]["score"] == 72.5 and rows[0]["triage"] == "apply"
    assert rows[0]["reason"] == "good fit"
    conn.close()


def test_cv_variants(tmp_path):
    conn = storage.connect(temp_db_path(tmp_path))
    vid = storage.save_cv_variant(conn, "robotics", "{'summary': '...'}", "Robotics Engineer")
    rows = storage.list_cv_variants(conn)
    assert vid == rows[0]["id"]
    conn.close()
