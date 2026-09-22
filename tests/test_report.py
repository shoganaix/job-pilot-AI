"""Tests for the Fase 4 HTML dashboard report."""

from jobpilot import storage
from jobpilot.config import load_config
from jobpilot.models import AppStatus, DimensionScore, Offer, Score, Triage
from jobpilot.pipeline.report import build_report


def _seed(conn):
    run = storage.run_start(conn, notes="score test")
    offers = [
        Offer(source="test", source_id="a", title="Junior ROS Engineer",
              company="Acme <script>alert(1)</script>", location="Madrid",
              description="ROS2 C++ for mobile robots."),
        Offer(source="test", source_id="b", title="QA Engineer", company="Beta",
              location="Remote", description="Quality and testing."),
        Offer(source="test", source_id="c", title="Irrelevant Job", company="Gamma",
              location="Paris", description="Sales."),
    ]
    storage.upsert_offers(conn, run.id, offers)
    ids = [r["id"] for r in conn.execute("SELECT id FROM offers ORDER BY id").fetchall()]
    storage.save_scores(conn, run.id, [
        Score(offer_id=ids[0], run_id=run.id, total=72.0, triage=Triage.APPLY,
              breakdown={
                  "skills": DimensionScore(80.0, 30.0, "hit"),
                  "experience": DimensionScore(60.0, 20.0, "junior"),
              },
              reason="ok"),
        Score(offer_id=ids[1], run_id=run.id, total=55.0, triage=Triage.REVIEW,
              breakdown={"skills": DimensionScore(40.0, 30.0, "partial")}),
        Score(offer_id=ids[2], run_id=run.id, total=20.0, triage=Triage.DISCARD, hard_filters=["clearance"]),
    ])
    storage.set_application(conn, ids[0], AppStatus.APPLY, notes="primera",
                            cv_file="output/cv/cv_1_en.md")
    return run, ids


def test_build_report_writes_escaped_html(tmp_path):
    config = load_config()
    conn = storage.connect(tmp_path / "db.sqlite")
    run, ids = _seed(conn)
    out = build_report(config, conn, out=tmp_path / "report.html")
    html = out.read_text(encoding="utf-8")
    assert out.exists()
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html
    assert f"run#{run.id}" in html
    assert "cv_1_en.md" in html
    assert "Junior ROS Engineer" in html
    assert "Resumen" in html and "Cola de aplicaciones" in html
    assert "aplicado" in html and "antigüedad" in html  # queue 2.0 columns
    assert "Familias" in html
    assert "apply</span>" in html
    assert str(ids[0]) in html and str(ids[1]) in html
    conn.close()


def test_build_report_family_filter(tmp_path):
    config = load_config()
    conn = storage.connect(tmp_path / "db.sqlite")
    _seed(conn)
    out = build_report(config, conn, family="general", out=tmp_path / "report.html")
    html = out.read_text(encoding="utf-8")
    assert "filtro familia: general" in html
    assert "Junior ROS Engineer" in html
    conn.close()


def test_build_report_empty(tmp_path):
    config = load_config()
    conn = storage.connect(tmp_path / "db.sqlite")
    out = build_report(config, conn, out=tmp_path / "report.html")
    html = out.read_text(encoding="utf-8")
    assert "La cola está vacía" in html
    assert "Sin puntúaciones" in html
    conn.close()


def test_latest_scored_run_helper(tmp_path):
    conn = storage.connect(tmp_path / "db.sqlite")
    assert storage.latest_scored_run(conn) is None
    run, _ids = _seed(conn)
    assert storage.latest_scored_run(conn) == run.id
    conn.close()
