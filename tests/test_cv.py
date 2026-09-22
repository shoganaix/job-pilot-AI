"""Tests for the tailored CV pipeline (prompt, validation, render, e2e)."""

from pathlib import Path

import pytest

from jobpilot import storage
from jobpilot.config import load_config
from jobpilot.llm import LLMError, _collect_text, extract_json
from jobpilot.models import Offer
from jobpilot.pipeline import cv as cvmod
from jobpilot.pipeline.cv import (
    CVError,
    generate_cv,
    heuristic_cv,
    render_markdown,
    render_pdf,
    validate_cv,
)


def _offer(**kw) -> Offer:
    defaults = dict(
        source="test",
        source_id="1",
        title="Junior Robotics Engineer",
        company="Acme Robotics",
        location="Madrid, Spain",
        description="ROS2 and C++ for a mobile robot.",
    )
    defaults.update(kw)
    return Offer(**defaults)


def _seeded_conn(tmp_path):
    conn = storage.connect(tmp_path / "t.db")
    run = storage.run_start(conn, notes="test")
    stats = storage.upsert_offers(conn, run.id, [_offer()])
    offer_id = conn.execute("SELECT id FROM offers").fetchone()["id"]
    return conn, offer_id, stats


# --------------------------------------------------------------------------- #
# llm helpers


def test_collect_text_concatenates_text_events():
    stream = "\n".join(
        [
            '{"type":"step_start"}',
            '{"type":"text","part":{"text":"hello "}}',
            '{"type":"text","part":{"text":"world"}}',
            '{"type":"step_finish"}',
        ]
    )
    assert _collect_text(stream) == "hello world"


def test_extract_json_fenced_and_nested():
    assert extract_json('```json\n{"a": {"b": 2}}\n```') == {"a": {"b": 2}}
    assert extract_json('noise before {"x": [1, {"y": "}"}]} noise') == {
        "x": [1, {"y": "}"}]
    }


def test_extract_json_raises_when_missing():
    with pytest.raises(LLMError):
        extract_json("no json here at all")


# --------------------------------------------------------------------------- #
# validation / render


def test_validate_cv_accepts_and_coerces():
    cv = validate_cv(
        {
            "name": "Maria",
            "title": "Robotics Engineer",
            "summary": "Summary.",
            "contact": {"email": "a@b.c", "phone": None},
            "sections": [
                {"heading": "Skills", "items": [{"label": "Python", "text": "expert"}]},
                {"heading": "Bad", "items": "not-a-dict"},
            ],
        }
    )
    assert cv["contact"] == {"email": "a@b.c"}
    assert cv["sections"][0]["items"][0]["title"] == "Python"
    assert len(cv["sections"]) == 1  # malformed section dropped


def test_validate_cv_rejects_incomplete():
    with pytest.raises(CVError):
        validate_cv({"name": "x", "summary": "", "sections": []})
    with pytest.raises(CVError):
        validate_cv("not a dict")


def test_render_markdown_shape():
    cv = validate_cv(
        {
            "name": "Maria",
            "title": "Robotics Engineer",
            "summary": "S.",
            "contact": {"email": "a@b.c"},
            "sections": [
                {
                    "heading": "Experience",
                    "items": [
                        {
                            "title": "Dev",
                            "subtitle": "Acme",
                            "date": "2023–2024",
                            "bullets": ["Did robots"],
                        }
                    ],
                }
            ],
        }
    )
    md = render_markdown(cv)
    assert md.startswith("# Maria")
    assert "## Experience" in md
    assert "- Did robots" in md
    assert "**Dev — Acme** · 2023–2024" in md


def test_render_pdf_creates_file(tmp_path):
    cv = heuristic_cv(load_config().master("es"), _offer(), {"skills": {}}, "es")
    out = render_pdf(cv, tmp_path / "cv.pdf")
    assert out.exists() and out.stat().st_size > 500
    assert out.read_bytes()[:4] == b"%PDF"


# --------------------------------------------------------------------------- #
# heuristic + e2e


def test_heuristic_cv_uses_offer_title_and_sections():
    config = load_config()
    master = config.master("es")
    cv = heuristic_cv(master, _offer(), {"skills": {"ros2": 9, "python": 8}}, "es")
    assert cv["title"] == "Junior Robotics Engineer"
    headings = [s["heading"] for s in cv["sections"]]
    assert headings[0] == "Competencias técnicas"
    assert "Experiencia profesional" in headings
    assert "Educación" in headings
    # groups with matched skills float to the top
    assert cv["sections"][0]["items"][0]["title"] in {"En camino (robótica/embedded)", "Lenguajes"}
    en = heuristic_cv(config.master("en"), _offer(), {"skills": {}}, "en")
    assert en["sections"][0]["heading"] == "Technical Skills"


def test_generate_cv_heuristic_end_to_end(tmp_path):
    config = load_config()
    conn, offer_id, stats = _seeded_conn(tmp_path)
    assert stats["test"][0] == 1
    result = generate_cv(config, conn, offer_id, lang="en", use_llm=False, out_dir=tmp_path)
    assert result["meta"]["backend"] == "heuristic"
    assert result["meta"]["lang"] == "en"
    assert Path(result["files"]["md"]).exists()
    assert Path(result["files"]["pdf"]).exists()
    assert "Junior Robotics Engineer" in result["markdown"]
    variants = storage.list_cv_variants(conn)
    assert len(variants) == 1
    conn.close()


def test_generate_cv_llm_success(monkeypatch, tmp_path):
    config = load_config()
    conn, offer_id, _ = _seeded_conn(tmp_path)
    monkeypatch.setattr(
        cvmod,
        "complete_json",
        lambda *a, **k: {
            "name": "Maria",
            "title": "Robotics Engineer",
            "summary": "Tailored.",
            "contact": {"email": "x@y.z"},
            "sections": [{"heading": "Skills", "items": [{"title": "ROS2", "text": "9/10"}]}],
        },
    )
    result = generate_cv(config, conn, offer_id, lang="es", out_dir=tmp_path)
    assert result["meta"]["backend"] == "llm"
    assert result["meta"]["fallback"] is None
    assert "Tailored." in result["markdown"]
    conn.close()


def test_generate_cv_llm_failure_falls_back(monkeypatch, tmp_path):
    config = load_config()
    conn, offer_id, _ = _seeded_conn(tmp_path)

    def boom(*a, **k):
        raise LLMError("opencode missing")

    monkeypatch.setattr(cvmod, "complete_json", boom)
    result = generate_cv(config, conn, offer_id, lang="es", out_dir=tmp_path)
    assert result["meta"]["backend"] == "heuristic"
    assert "opencode missing" in result["meta"]["fallback"]
    conn.close()


def test_generate_cv_unknown_offer(tmp_path):
    config = load_config()
    conn = storage.connect(tmp_path / "t.db")
    with pytest.raises(CVError, match="not found"):
        generate_cv(config, conn, 999, use_llm=False, out_dir=tmp_path)
    conn.close()
