"""Tests for the local web UI: YAML IO, form payloads and HTTP routes."""

from __future__ import annotations

import threading

import httpx
import pytest
import yaml

from jobpilot.config import (
    ConfigError,
    parse_families,
    parse_master_cv,
    parse_profile,
    parse_search,
)
from jobpilot.webui import payload, yaml_io
from jobpilot.webui.server import make_server

from ._util import SCAFFOLDS, sample_config


# --------------------------------------------------------------------------- #
# yaml_io
# --------------------------------------------------------------------------- #
def test_save_yaml_keeps_backup(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text("a: 1\n", encoding="utf-8")
    yaml_io.save_yaml(path, {"a": 2})
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == {"a": 2}
    assert yaml.safe_load(
        yaml_io.backup_name(path).read_text(encoding="utf-8")
    ) == {"a": 1}


def test_load_yaml_missing_file_is_empty(tmp_path):
    assert yaml_io.load_yaml(tmp_path / "nope.yaml") == {}


def test_validate_master_cv_accepts_scaffold(tmp_path):
    data = yaml.safe_load(
        (SCAFFOLDS / "master_cv.yaml").read_text(encoding="utf-8")
    )
    yaml_io.validate_master_cv(data)  # no raise


def test_validate_master_cv_rejects_missing_section():
    with pytest.raises(ConfigError, match="contact"):
        yaml_io.validate_master_cv({"summary": {}, "experience": [],
                                    "education": [], "skills": []})


def test_validate_profile_accepts_scaffold():
    data = yaml.safe_load((SCAFFOLDS / "profile.yaml").read_text(encoding="utf-8"))
    yaml_io.validate_profile(data)  # no raise


def test_validate_profile_rejects_family_without_queries():
    data = yaml.safe_load((SCAFFOLDS / "profile.yaml").read_text(encoding="utf-8"))
    data["families"][0].pop("queries")
    with pytest.raises(ConfigError, match="queries"):
        yaml_io.validate_profile(data)


def test_validate_profile_rejects_unknown_ats_source():
    data = yaml.safe_load((SCAFFOLDS / "profile.yaml").read_text(encoding="utf-8"))
    data["ats_companies"]["workday"] = ["acme"]
    with pytest.raises(ConfigError, match="workday"):
        yaml_io.validate_profile(data)


# --------------------------------------------------------------------------- #
# payload: field helpers
# --------------------------------------------------------------------------- #
def test_rows_survive_deleted_indices():
    form = {
        "exp.0.company": ["A"],
        "exp.2.company": ["B"],
        "exp.5.company": ["C"],
        "other.0.company": ["ignored"],
    }
    rows = payload.rows(form, "exp")
    assert [idx for idx, _ in rows] == [0, 2, 5]
    assert rows[1][1]["company"] == "B"


def test_row_pairs_skips_fully_blank_rows():
    form = {"exp.0.company": [""], "exp.1.company": ["Acme"]}
    assert payload.row_pairs(form, "exp", ("company",)) == [{"company": "Acme"}]


def test_lines_and_field_defaults():
    form = {"queries": [" ros \n\npython "]}
    assert payload.lines(form, "queries") == ["ros", "python"]
    assert payload.field(form, "absent") == ""
    assert payload.field(form, "absent", "d") == "d"
    assert not payload.checked(form, "absent")
    assert payload.checked(form, "x") is False
    form["x"] = ["1"]
    assert payload.checked(form, "x")


def test_number_rejects_garbage():
    form = {"n": ["abc"]}
    with pytest.raises(ConfigError, match="n"):
        payload.number(form, "n", 10, int)


def test_bilingual_pairs_line_by_line():
    assert payload.bilingual("uno\ndos", "one\ntwo") == [
        {"es": "uno", "en": "one"},
        {"es": "dos", "en": "two"},
    ]
    # a line blank on both sides disappears, shorter side is padded
    assert payload.bilingual("a\n\nb", "only-a") == [
        {"es": "a", "en": "only-a"},
        {"es": "b", "en": ""},
    ]


# --------------------------------------------------------------------------- #
# payload: builders
# --------------------------------------------------------------------------- #
def test_build_master_cv_roundtrip():
    cv = yaml.safe_load((SCAFFOLDS / "master_cv.yaml").read_text(encoding="utf-8"))
    first_group, first_items = next(iter(cv["skills"].items()))
    form = {
        "contact.name": [cv["contact"]["name"]],
        "contact.email": [cv["contact"].get("email", "")],
        "summary.es": [cv["summary"]["es"]],
        "summary.en": [cv["summary"].get("en", "")],
        "exp.0.company": [cv["experience"][0]["company"]],
        "exp.0.role_es": [cv["experience"][0]["role"]["es"]],
        "exp.0.role_en": [cv["experience"][0]["role"].get("en", "")],
        "exp.0.start": [cv["experience"][0].get("start", "")],
        "exp.0.end": [cv["experience"][0].get("end", "")],
        "exp.0.bullets_es": [
            "\n".join(b["es"] for b in cv["experience"][0]["bullets"])
        ],
        "exp.0.bullets_en": [
            "\n".join(b.get("en", "") for b in cv["experience"][0]["bullets"])
        ],
        "edu.0.degree_es": [cv["education"][0]["degree"]["es"]],
        "edu.0.degree_en": [cv["education"][0]["degree"].get("en", "")],
        "edu.0.school": [cv["education"][0]["school"]],
        "edu.0.start": [cv["education"][0].get("start", "")],
        "edu.0.end": [cv["education"][0].get("end", "")],
        "sgrp.0.group": [first_group],
        "sgrp.0.items": ["\n".join(first_items)],
    }
    out = payload.build_master_cv(form)
    yaml_io.validate_master_cv(out)
    assert out["contact"]["name"] == cv["contact"]["name"]
    assert out["experience"][0]["company"] == cv["experience"][0]["company"]
    assert out["experience"][0]["bullets"][0]["es"]
    assert out["skills"] == {first_group: list(first_items)}


def test_build_master_cv_full_scaffold_roundtrip():
    """Render every scaffold field through form fields and get it back equal."""
    cv = yaml.safe_load((SCAFFOLDS / "master_cv.yaml").read_text(encoding="utf-8"))
    form: dict[str, list[str]] = {
        **{f"contact.{k}": [str(v)] for k, v in cv["contact"].items()},
        "summary.es": [cv["summary"]["es"]],
        "summary.en": [cv["summary"].get("en", "")],
    }
    for i, exp in enumerate(cv["experience"]):
        form[f"exp.{i}.company"] = [exp["company"]]
        form[f"exp.{i}.role_es"] = [exp["role"]["es"]]
        form[f"exp.{i}.role_en"] = [exp["role"].get("en", "")]
        form[f"exp.{i}.start"] = [exp.get("start", "")]
        form[f"exp.{i}.end"] = [exp.get("end", "")]
        form[f"exp.{i}.bullets_es"] = ["\n".join(b["es"] for b in exp["bullets"])]
        form[f"exp.{i}.bullets_en"] = [
            "\n".join(b.get("en", "") for b in exp["bullets"])
        ]
    for i, edu in enumerate(cv["education"]):
        form[f"edu.{i}.degree_es"] = [edu["degree"]["es"]]
        form[f"edu.{i}.degree_en"] = [edu["degree"].get("en", "")]
        form[f"edu.{i}.school"] = [edu["school"]]
        form[f"edu.{i}.start"] = [edu.get("start", "")]
        form[f"edu.{i}.end"] = [edu.get("end", "")]
    for i, (group, items) in enumerate(cv["skills"].items()):
        form[f"sgrp.{i}.group"] = [group]
        form[f"sgrp.{i}.items"] = ["\n".join(items)]
    for i, proj in enumerate(cv["projects"]):
        form[f"proj.{i}.name_es"] = [proj["name"]["es"]]
        form[f"proj.{i}.name_en"] = [proj["name"].get("en", "")]
        form[f"proj.{i}.url"] = [proj.get("url", "")]
        form[f"proj.{i}.desc_es"] = [proj["description"]["es"]]
        form[f"proj.{i}.desc_en"] = [proj["description"].get("en", "")]
    for i, cert in enumerate(cv["certifications"]):
        form[f"cert.{i}.name_es"] = [cert["name"]["es"]]
        form[f"cert.{i}.name_en"] = [cert["name"].get("en", "")]
        form[f"cert.{i}.issuer"] = [cert.get("issuer", "")]
        form[f"cert.{i}.year"] = [cert.get("year", "")]
        form[f"cert.{i}.note_es"] = [cert["note"]["es"]]
        form[f"cert.{i}.note_en"] = [cert["note"].get("en", "")]

    out = payload.build_master_cv(form)
    yaml_io.validate_master_cv(out)
    assert out == cv


def test_build_master_cv_drops_blank_optional_sections():
    out = payload.build_master_cv({
        "contact.name": ["Ana"],
        "summary.es": [""],
        "summary.en": [""],
        "proj.0.name_es": [""],
        "cert.0.name_es": [""],
    })
    assert "projects" not in out
    assert "certifications" not in out
    assert out["experience"] == []


def test_build_profile_patch_and_merge():
    form = {
        "search.target_offers": ["123"],
        "search.max_results_per_query": ["50"],
        "search.max_pages_per_query": ["5"],
        "search.exclude_foreign_onsite": ["1"],
        "search.exclude_seniority": ["senior", "lead"],
        "sloc.0.name": ["Spain"],
        "sloc.0.country": ["es"],
        "profile.seniority_target": ["midlevel"],
        "profile.languages": ["es, en"],
        "ploc.0.area": ["Madrid (Spain)"],
        "ploc.0.kind": ["onsite"],
        "ploc.0.weight": ["70"],
        "profile.exclude_companies": ["BigTech\nOtherCo"],
        "ats.greenhouse": ["acme"],
        "ats.lever": [],
    }
    patch = payload.build_profile_patch(form)
    assert patch["search"]["target_offers"] == 123
    assert patch["search"]["max_pages_per_query"] == 5
    assert patch["search"]["exclude_foreign_onsite"] is True
    assert patch["search"]["exclude_seniority"] == ["senior", "lead"]
    assert patch["search"]["locations"] == [
        {"name": "Spain", "adzuna_country": "es"}
    ]
    assert patch["profile"]["seniority_target"] == "midlevel"
    assert patch["profile"]["languages"] == ["es", "en"]
    assert patch["profile"]["locations"][0] == {
        "area": "Madrid (Spain)", "kind": "onsite", "weight": 70.0,
    }
    assert patch["profile"]["exclude_companies"] == ["BigTech", "OtherCo"]
    assert patch["ats_companies"] == {"greenhouse": ["acme"], "lever": []}

    original = yaml.safe_load(
        (SCAFFOLDS / "profile.yaml").read_text(encoding="utf-8")
    )
    merged = payload.apply_profile_patch(original, patch)
    assert merged["scoring"] == original["scoring"]  # untouched
    assert merged["project"] == original["project"]
    assert merged["families"] == original["families"]
    parse_search(merged["search"])
    parse_profile(merged["profile"])


def test_build_family_updates_only_form_fields():
    fam = {
        "id": "robotics",
        "label": "old",
        "weight": 1.0,
        "interest": 10,
        "queries": ["old query"],
        "sources": ["adzuna"],
        "skills": {"ros": 9},
        "search_locations": [{"name": "Spain"}],
    }
    form = {
        "family.label": ["Robotics"],
        "family.weight": ["1.5"],
        "family.interest": ["8"],
        "family.queries": ["ROS Developer\nROS2 Developer"],
        "family.sources": ["adzuna", "remoteok"],
        "family.adzuna.es": ["robótica"],
        "family.adzuna.de": [],
        "family.seniority_hint": [""],
        "fskill.0.name": ["ros"],
        "fskill.0.weight": ["9"],
        "fskill.1.name": ["slam"],
        "fskill.1.weight": ["7"],
    }
    out = payload.build_family(form, fam)
    assert out["label"] == "Robotics"
    assert out["weight"] == 1.5
    assert out["queries"] == ["ROS Developer", "ROS2 Developer"]
    assert out["sources"] == ["adzuna", "remoteok"]
    assert out["skills"] == {"ros": 9.0, "slam": 7.0}
    assert out["adzuna_queries"] == {"es": ["robótica"]}
    assert out["search_locations"] == [{"name": "Spain"}]  # preserved
    assert "seniority_hint" not in out


def test_build_family_requires_queries_and_sources():
    fam = {"id": "x", "queries": ["q"], "sources": ["adzuna"]}
    with pytest.raises(ConfigError, match="query"):
        payload.build_family({"family.sources": ["adzuna"]}, fam)
    with pytest.raises(ConfigError, match="fuente"):
        payload.build_family({"family.queries": ["q"]}, fam)


# --------------------------------------------------------------------------- #
# HTTP server
# --------------------------------------------------------------------------- #
@pytest.fixture()
def web(tmp_path):
    """Server wired to a scaffolded workspace, running on an ephemeral port.

    The path assertions are load-bearing: an earlier bug (``master_cv_path``
    defaulting to the repo's config/) made the suite overwrite the real CV.
    """
    config = sample_config(tmp_path)
    assert config.profile_path.is_relative_to(tmp_path)
    assert config.master_cv_path.is_relative_to(tmp_path)
    httpd = make_server(config.profile_path, config.master_cv_path, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    yield {
        "base": f"http://127.0.0.1:{port}",
        "port": port,
        "profile": config.profile_path,
        "cv": config.master_cv_path,
    }
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def test_home_and_forms_render(web):
    with httpx.Client(base_url=web["base"]) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "Mi CV" in home.text and "Preferencias" in home.text

        cv = client.get("/cv")
        assert cv.status_code == 200
        assert 'name="contact.name"' in cv.text
        assert 'name="exp.0.company"' in cv.text

        prefs = client.get("/prefs")
        assert prefs.status_code == 200
        assert 'name="search.exclude_seniority"' in prefs.text

        fams = client.get("/families")
        assert fams.status_code == 200
        assert "/families/robotics" in fams.text

        edit = client.get("/families/robotics")
        assert edit.status_code == 200
        assert 'name="family.queries"' in edit.text

        missing = client.get("/families/nope")
        assert missing.status_code == 404


def test_post_cv_writes_file_with_backup(web):
    with httpx.Client(base_url=web["base"]) as client:
        resp = client.post("/cv", data={
            "contact.name": ["Ana Prueba"],
            "contact.email": ["ana@example.com"],
            "contact.city": ["Madrid"],
            "summary.es": ["Resumen es"],
            "summary.en": ["Summary en"],
            "exp.0.company": ["Acme"],
            "exp.0.role_es": ["Ingeniera"],
            "exp.0.role_en": ["Engineer"],
            "exp.0.start": ["01/2023"],
            "exp.0.end": ["actual"],
            "exp.0.bullets_es": ["Logro uno"],
            "exp.0.bullets_en": ["Shipped thing"],
            "edu.0.degree_es": ["Grado"],
            "edu.0.degree_en": ["BSc"],
            "edu.0.school": ["UCM"],
            "sgrp.0.group": ["Lenguajes"],
            "sgrp.0.items_es": ["python"],
            "sgrp.0.items_en": ["python"],
        }, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/cv?ok=1"

    saved = yaml.safe_load(web["cv"].read_text(encoding="utf-8"))
    assert saved["contact"]["name"] == "Ana Prueba"
    assert saved["experience"][0]["bullets"] == [
        {"es": "Logro uno", "en": "Shipped thing"}
    ]
    backup = yaml.safe_load(yaml_io.backup_name(web["cv"]).read_text(encoding="utf-8"))
    assert backup["contact"]["name"] != "Ana Prueba"  # previous CV kept
    parse_master_cv(web["cv"])  # the CLI can still read it


def test_invalid_cv_post_keeps_file_intact(web, monkeypatch):
    """A validator rejection must re-render the form and never touch disk.

    ``build_master_cv`` always emits every required section, so the only way
    the CV payload can be rejected is the validator itself failing (e.g. a
    structural rule tightened later) — patch it to exercise that branch.
    """
    original = web["cv"].read_bytes()

    def boom(data):
        raise ConfigError("sección experience inválida")

    monkeypatch.setattr(yaml_io, "validate_master_cv", boom)
    with httpx.Client(base_url=web["base"]) as client:
        resp = client.post("/cv", data={
            "contact.name": ["Sin secciones"],
            "summary.es": [""],
        }, follow_redirects=False)
    assert resp.status_code == 400
    assert "No se guardó" in resp.text
    assert "experience inválida" in resp.text
    assert web["cv"].read_bytes() == original
    assert not yaml_io.backup_name(web["cv"]).exists()  # no backup for a no-op


def test_prefs_post_with_bad_number_is_rejected(web):
    """Real end-to-end validation error: a non-numeric field changes nothing."""
    original = web["profile"].read_bytes()
    with httpx.Client(base_url=web["base"]) as client:
        resp = client.post("/prefs", data={
            "search.target_offers": ["mucho"],
            "search.max_results_per_query": ["50"],
            "search.max_pages_per_query": ["2"],
            "profile.seniority_target": ["junior"],
            "profile.languages": ["es, en"],
        }, follow_redirects=False)
    assert resp.status_code == 400
    assert "No se guardó" in resp.text
    assert web["profile"].read_bytes() == original


def test_post_prefs_patches_search_and_keeps_scoring(web):
    before = yaml.safe_load(web["profile"].read_text(encoding="utf-8"))
    with httpx.Client(base_url=web["base"]) as client:
        resp = client.post("/prefs", data={
            "search.target_offers": ["444"],
            "search.max_results_per_query": ["50"],
            "search.max_pages_per_query": ["3"],
            "search.exclude_seniority": ["senior"],
            "sloc.0.name": ["Spain"],
            "sloc.0.country": ["es"],
            "profile.seniority_target": ["junior"],
            "profile.languages": ["es, en"],
            "profile.exclude_companies": [""],
            "ploc.0.area": ["Madrid (Spain)"],
            "ploc.0.kind": ["onsite"],
            "ploc.0.weight": ["70"],
        }, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/prefs?ok=1"

    after = yaml.safe_load(web["profile"].read_text(encoding="utf-8"))
    assert after["search"]["target_offers"] == 444
    assert after["search"]["exclude_seniority"] == ["senior"]
    assert after["scoring"] == before["scoring"]
    assert after["families"] == before["families"]
    assert after["project"] == before["project"]


def test_post_family_saves_one_family(web):
    with httpx.Client(base_url=web["base"]) as client:
        resp = client.post("/families/robotics", data={
            "family.label": "Robotics & Autonomous",
            "family.interest": "10",
            "family.weight": "1.0",
            "family.queries": "ROS Developer\nJunior ROS Developer",
            "family.sources": ["adzuna", "hn_hiring"],
            "family.adzuna.es": "robótica",
            "family.adzuna.de": "",
            "fskill.0.name": "ros",
            "fskill.0.weight": "9",
        }, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/families/robotics?ok=1"

    saved = yaml.safe_load(web["profile"].read_text(encoding="utf-8"))
    robotics = next(f for f in saved["families"] if f["id"] == "robotics")
    assert robotics["queries"] == ["ROS Developer", "Junior ROS Developer"]
    assert robotics["sources"] == ["adzuna", "hn_hiring"]
    assert robotics["skills"] == {"ros": 9.0}
    embedded = next(f for f in saved["families"] if f["id"] == "embedded")
    assert embedded["queries"]  # other families untouched
    parse_families(saved["families"])


def test_post_family_with_no_queries_rejected(web):
    before = web["profile"].read_bytes()
    with httpx.Client(base_url=web["base"]) as client:
        resp = client.post("/families/robotics", data={
            "family.queries": "",
            "family.sources": ["adzuna"],
        }, follow_redirects=False)
    assert resp.status_code == 400
    assert web["profile"].read_bytes() == before


def test_post_rejects_foreign_host_header(web):
    import socket

    body = "contact.name=Ana"
    request = (
        f"POST /cv HTTP/1.1\r\n"
        f"Host: evil.example\r\n"
        f"Content-Type: application/x-www-form-urlencoded\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n\r\n{body}"
    )
    with socket.create_connection(("127.0.0.1", web["port"]), timeout=5) as sock:
        sock.sendall(request.encode("ascii"))
        raw = sock.recv(4096).decode("latin-1")
    assert raw.splitlines()[0].endswith("403 Forbidden")


def test_unknown_route_is_404(web):
    with httpx.Client(base_url=web["base"]) as client:
        assert client.get("/nowhere").status_code == 404
        assert client.post("/nowhere", follow_redirects=False).status_code == 404
