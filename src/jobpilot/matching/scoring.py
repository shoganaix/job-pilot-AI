"""Scoring engine: six weighted dimensions -> 0-100 + triage.

Dimensions (profile ``scoring.weights``, default sum 100):

  skills     30  how much of the offer's required skill weight we already cover
  experience 20  junior->senior fit vs the target seniority
  education  10  degree level fit
  location   15  how well the offer's location matches the profile prefs
  seniority  15  explicit seniority label vs the target seniority
  interest   10  the family's configured interest weight

Hard rules (citizenship, clearance, US-only, excluded companies) short-circuit
to ``Triage.DISCARD`` regardless of score.
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..models import Triage
from .extract import extract_hard_filters, extract_offer_signals

_SENIORITY_RANK = {"lead": 20.0, "senior": 40.0, "midlevel": 70.0, "junior": 100.0, "entry": 100.0}


def master_skill_variants(config: Config) -> dict[str, float]:
    """Normalized CV skill variants -> coverage factor.

    Skills in the "En camino..." (learning) group count half: we can speak to
    them but they are not production experience yet.
    """
    variants: dict[str, float] = {}
    for group, items in config.master_cv.skills.items():
        factor = 0.5 if "camino" in group.lower() else 1.0
        for item in items:
            for alias in _alias_variants(str(item)):
                variants.setdefault(alias, factor)
    return variants


def _alias_variants(name: str) -> set[str]:
    from .taxonomy import skill_tokens, skill_variants

    return skill_variants(name) | skill_tokens(name)


def _skills_dimension(found_skills: dict[str, float], family, config: Config) -> dict[str, Any]:
    total_weight = sum(family.skills.values()) or 1.0
    have = master_skill_variants(config)
    found_aliases = {s: set(_alias_variants(s)) for s in found_skills}
    missing: list[str] = []
    covered_weight = 0.0
    for s, wt in found_skills.items():
        factor = max((have[a] for a in found_aliases[s] if a in have), default=0.0)
        if factor:
            covered_weight += wt * factor
        else:
            missing.append(s)
    found_weight = sum(found_skills.values())
    found_ratio = found_weight / total_weight if found_skills else 0.0
    covered_ratio = covered_weight / found_weight if found_weight else 0.0
    value = 100.0 * found_ratio * (0.5 + 0.5 * covered_ratio)
    evidence = (
        f"{len(found_skills)} skill hits "
        f"({found_weight:.0f}/{total_weight:.0f} domain weight), covered={covered_ratio:.0%}"
        + (f"; sin cubrir: {', '.join(missing[:6])}" if missing else "")
    )
    return {"value": round(value, 1), "evidence": evidence}


def _seniority_value(seniority: str | None, years: int | None) -> float:
    rank = _SENIORITY_RANK.get(seniority) if seniority else None
    if rank is not None:
        return rank
    if years is None:
        return 60.0  # unknown -> neutral
    if years <= 3:
        return 90.0
    if years <= 6:
        return 60.0
    if years <= 10:
        return 35.0
    return 20.0


def _experience_value(seniority: str | None, years: int | None, target: str) -> dict[str, Any]:
    base = _seniority_value(seniority, years)
    if target == "senior":
        base = 100.0 - base + (60.0 if seniority == "senior" else 0.0)
    value = round(min(100.0, max(0.0, base)), 1)
    bits = [f"seniority={seniority or 'n/a'}", f"years={years}"]
    return {"value": value, "evidence": "; ".join(bits)}


def _education_value(level: str | None, config: Config) -> dict[str, Any]:
    education = config.master_cv.education or []
    have_degree = bool(education)
    if level is None:
        value = 80.0  # no mention -> neutral, wait for education dimension
    elif level == "bachelor":
        value = 90.0 if have_degree else 40.0
    elif level == "master":
        value = 100.0 if have_degree else 55.0
    elif level == "phd":
        value = 45.0  # we don't have a PhD
    return {"value": round(value, 1), "evidence": f"required={level or 'none'}"}


def _location_value(loc: dict[str, Any]) -> dict[str, Any]:
    return {"value": round(loc["weight"], 1), "evidence": f"area={loc['area']} ({loc['kind']})"}


def _interest_value(family) -> dict[str, Any]:
    interest = getattr(family, "interest", 10.0) or 10.0
    value = min(100.0, max(0.0, interest * 10.0))
    return {"value": round(value, 1), "evidence": f"family interest={interest}/10"}


def score_offer(offer, family, config: Config) -> dict[str, Any]:
    """Score one offer against one family. Returns raw signals + dimensions."""
    signals = extract_offer_signals(offer, family, config)
    hard_filters = extract_hard_filters(offer, config)
    if hard_filters:
        triage = Triage.DISCARD
    w = config.scoring.weights
    skills = _skills_dimension(signals["skills"], family, config)
    seniority = _seniority_value(signals["seniority"], signals["experience_years"])
    experience = _experience_value(signals["seniority"], signals["experience_years"], config.profile.seniority_target)
    education = _education_value(signals["education"], config)
    location = _location_value(signals["location"])
    interest = _interest_value(family)

    dims = {
        "skills": skills,
        "experience": experience,
        "education": education,
        "location": location,
        "seniority": {"value": round(seniority, 1), "evidence": f"target={config.profile.seniority_target}"},
        "interest": interest,
    }

    total = sum(
        dims[name]["value"] * (w.get(name, 0) or 0)
        for name in dims
    ) / 100.0

    if hard_filters:
        triage = Triage.DISCARD
    elif total >= config.scoring.threshold and skills["value"] >= getattr(
        config.scoring, "min_skills_for_apply", 20.0
    ):
        triage = Triage.APPLY
    elif total >= config.scoring.review_threshold:
        triage = Triage.REVIEW
    else:
        triage = Triage.DISCARD

    return {
        "total": round(total, 1),
        "triage": triage,
        "breakdown": {
            name: {"value": dims[name]["value"], "weight": w.get(name, 0), "evidence": dims[name]["evidence"]}
            for name in dims
        },
        "extracted": signals,
        "hard_filters": hard_filters,
        "reason": f"{len(hard_filters)} hard filters" if hard_filters else str(triage.value),
    }
