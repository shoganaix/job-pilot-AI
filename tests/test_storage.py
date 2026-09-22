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

    storage.set_application(conn, oid, AppStatus.APPLIED)
    rows = storage.list_applications(conn, statuses=[AppStatus.APPLY])
    assert rows == []
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
