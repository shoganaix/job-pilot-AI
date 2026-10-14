"""Tests for the YAML configuration loader."""

import pytest

from jobpilot.config import ConfigError, load_config

from ._util import sample_config


def test_default_profile_loads(tmp_path):
    config = sample_config(tmp_path)
    assert len(config.families) >= 7
    assert sum(config.scoring.weights.values()) == pytest.approx(100, abs=0.5)
    assert config.scoring.threshold == 65
    assert any(loc.adzuna_country == "es" for loc in config.search.locations)
    assert config.master_cv.contact["name"]


def test_family_lookup(tmp_path):
    config = sample_config(tmp_path)
    fam = config.family("robotics")
    assert "Robotics Engineer" in fam.queries
    assert fam.skills.get("ros") == 9


def test_missing_profile_raises():
    from pathlib import Path

    with pytest.raises(ConfigError, match="profile not found"):
        load_config(Path("nope/nope.yaml"))


def test_paths_are_anchored_to_the_repo_root(tmp_path):
    """Relative `project:` paths must not depend on the caller's cwd."""
    config = sample_config(tmp_path)
    assert config.db_path.is_absolute()
    assert config.output_dir.is_absolute()
    assert config.snapshot_dir.is_absolute()
    assert config.db_path == tmp_path / "jobpilot.db"
    assert config.output_dir == tmp_path / "output"


def test_absolute_paths_are_preserved(tmp_path):
    """A user pointing at their own storage keeps it."""
    from jobpilot.config import REPO_ROOT

    assert REPO_ROOT.is_absolute()
    config = sample_config(tmp_path)
    assert config.db_path.is_absolute()


def test_master_cv_bilingual_resolution(tmp_path):
    config = sample_config(tmp_path)
    es = config.master("es")
    en = config.master("en")
    assert isinstance(es.summary, str) and isinstance(en.summary, str)
    assert es.summary != en.summary
    # every narrative field resolves to a non-empty string per language
    assert isinstance(en.experience[0]["role"], str) and en.experience[0]["role"]
    assert isinstance(es.education[0]["degree"], str) and es.education[0]["degree"]
    assert isinstance(en.projects[0]["description"], str)
    assert isinstance(en.certifications[0]["name"], str)
    # skills and contact stay language-neutral
    assert en.skills == es.skills
    assert en.contact["name"] == es.contact["name"]


def test_master_cv_defaults_to_first_language(tmp_path):
    config = sample_config(tmp_path)
    master = config.master()
    assert master.contact["name"]
    assert master.summary
    # unknown langs fall back to the default
    assert config.master("fr").summary == master.summary


def test_missing_required_master_cv_key_raises(tmp_path):
    """parse_master_cv must reject a file that misses the required keys."""
    import yaml

    from jobpilot.config import parse_master_cv

    bad = tmp_path / "bad_cv.yaml"
    bad.write_text(yaml.safe_dump({"contact": {}}), encoding="utf-8")
    with pytest.raises(ConfigError, match="missing key"):
        parse_master_cv(bad)