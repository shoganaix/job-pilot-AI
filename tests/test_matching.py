"""Tests for the matching engine: taxonomy, extract, scoring."""


from jobpilot.config import load_config
from jobpilot.matching.extract import (
    extract_education,
    extract_experience_years,
    extract_location,
    extract_offer_signals,
    extract_skills,
)
from jobpilot.matching.scoring import score_offer
from jobpilot.matching.taxonomy import (
    normalize_skill,
    skill_aliases,
    skill_tokens,
    skill_variants,
)
from jobpilot.models import Offer, Triage


def _offer(**kw) -> Offer:
    defaults = dict(
        source="test",
        source_id="1",
        title="Test Engineer",
        company="Acme",
        location="",
        description="",
    )
    defaults.update(kw)
    return Offer(**defaults)


# --------------------------------------------------------------------------- #
# taxonomy


def test_normalize_skill_collapses_separators():
    assert normalize_skill("C++") == "c++"
    assert normalize_skill("ROS-2") == "ros2"
    assert normalize_skill("CI/CD") == "cicd"
    assert normalize_skill("Python 3.11") == "python3.11"


def test_skill_variants_keep_phrases():
    assert "test automation" in skill_variants("test automation")
    assert "real-time" in skill_variants("real time")  # hyphen flex
    assert "real time" in skill_variants("real time")


def test_skill_tokens_single_words_only():
    assert "python" in skill_tokens("python")
    assert "c++" in skill_tokens("c++")
    assert "testautomation" not in skill_tokens("test automation")
    assert all(" " not in t and "-" not in t for t in skill_tokens("test automation"))


def test_no_short_substring_tokens():
    tokens = skill_tokens("c")  # single 'c' must not survive
    assert "c" not in tokens
    assert "mcu" in skill_tokens("microcontroller")
    assert "stm32" in skill_tokens("stm32")


def test_power_no_longer_alias_of_power_electronics():
    assert "power" not in skill_tokens("power electronics")
    assert "power electronics" in skill_aliases("power electronics")


# --------------------------------------------------------------------------- #
# extract


def test_extract_skills_matches_phrases():
    offer = _offer(description="We do test automation and continuous integration.")
    found = extract_skills(offer, {"test automation": 7, "pytest": 6, "ci/cd": 6})
    assert set(found) == {"test automation", "ci/cd"}


def test_extract_skills_exact_tokens_only():
    offer = _offer(description="Experience with C++ and python for candidates in the EU.")
    found = extract_skills(offer, {"c++": 8, "can bus": 5, "python": 8})
    assert set(found) == {"c++", "python"}
    # "can" is not a word-matchable token from "can bus", so no hit here.
    assert "can bus" not in found


def test_extract_skills_ignores_substring_aliases():
    offer = _offer(title="Software Deployment Engineer", description="distributed systems")
    found = extract_skills(offer, {"testing": 8})
    assert found == {}


def test_extract_seniority_and_years():
    offer = _offer(description="Mid-level engineer, 3+ years of experience.")
    assert extract_experience_years(offer) == 3
    offer2 = _offer(description="Junior embedded engineer")
    from jobpilot.matching.extract import extract_seniority

    assert extract_seniority(offer2) == "junior"


def test_extract_education():
    assert extract_education(_offer(description="requires a Master's degree")) == "master"
    assert extract_education(_offer(description="BSc in EE or similar")) == "bachelor"


def test_extract_location_port_of_spain_is_not_eu():
    offer = _offer(source="remoteok", remote=True, location="Port of Spain, Trinidad")
    loc = extract_location(offer, load_config().profile)
    assert loc["area"] == "Foreign"
    assert loc["weight"] == 20.0


def test_extract_location_remote_eu():
    config = load_config()
    offer = _offer(source="himalayas", remote=True, location="Germany remote")
    loc = extract_location(offer, config.profile)
    assert loc["area"] == "Remote EU"
    assert loc["weight"] >= 90.0


def test_extract_location_remoteok_remote_flag_ignored():
    config = load_config()
    offer = _offer(source="remoteok", remote=True, location="Cincinnati, OH")
    loc = extract_location(offer, config.profile)
    assert loc["kind"] == "onsite"
    assert loc["area"] == "Foreign"


# --------------------------------------------------------------------------- #
# scoring


def test_score_offer_shape():
    config = load_config()
    family = config.family("robotics")
    offer = _offer(
        description=(
            "Junior Robotics Engineer using ROS/ROS2, C++ and Python for "
            "motion planning on real-time control systems."
        )
    )
    res = score_offer(offer, family, config)
    assert {"total", "triage", "breakdown", "extracted", "hard_filters", "reason"} <= set(res)
    assert {n for n in res["breakdown"]} == set(config.scoring.weights)
    assert res["hard_filters"] == []
    assert res["total"] > 0


def test_score_offer_hard_filter_discards():
    config = load_config()
    family = config.family("robotics")
    offer = _offer(description="Must be a US citizen, active security clearance required.")
    res = score_offer(offer, family, config)
    assert res["triage"] is Triage.DISCARD


def test_score_offer_low_skills_cannot_apply():
    config = load_config()
    family = config.family("electronics")
    offer = _offer(description="Junior quality assistant in Port of Spain, TT.")
    res = score_offer(offer, family, config)
    assert res["triage"] is not Triage.APPLY


def test_extract_offer_signals_complete():
    config = load_config()
    offer = _offer(description="Junior role, 2+ years, C++.", location="Madrid, Spain")
    sig = extract_offer_signals(offer, config.family("embedded"), config)
    assert sig["seniority"] == "junior"
    assert sig["experience_years"] == 2
    assert sig["location"]["area"] == "Spain"
    assert "c++" in sig["skills"]
