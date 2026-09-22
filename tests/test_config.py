"""Tests for the YAML configuration loader."""

import pytest

from jobpilot.config import ConfigError, load_config


def test_default_profile_loads(tmp_path):
    config = load_config()
    assert len(config.families) >= 7
    assert sum(config.scoring.weights.values()) == pytest.approx(100, abs=0.5)
    assert config.scoring.threshold == 65
    assert any(loc.adzuna_country == "es" for loc in config.search.locations)
    assert config.master_cv.contact["name"]


def test_family_lookup():
    config = load_config()
    fam = config.family("robotics")
    assert "Robotics Engineer" in fam.queries
    assert fam.skills.get("ros") == 9


def test_missing_profile_raises():
    from pathlib import Path

    with pytest.raises(ConfigError, match="profile not found"):
        load_config(Path("nope/nope.yaml"))


def test_master_cv_bilingual_resolution():
    config = load_config()
    es = config.master("es")
    en = config.master("en")
    assert isinstance(es.summary, str) and isinstance(en.summary, str)
    assert es.summary != en.summary
    assert en.experience[0]["role"] == "Programming Instructor"
    assert es.education[0]["degree"] == "Microgrado en Electrónica e Ingeniería de Automatización Industrial"
    assert isinstance(en.projects[0]["description"], str)
    assert isinstance(en.certifications[0]["name"], str)
    # skills and contact stay language-neutral
    assert en.skills == es.skills
    assert en.contact["name"] == es.contact["name"]


def test_master_cv_defaults_to_first_language():
    config = load_config()
    assert config.master().contact["name"] == "María Soriano"
    assert config.master("fr").summary  # unknown langs fall back to the default
