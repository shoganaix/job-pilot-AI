"""Configuration loading (.env + YAML profile) with light validation.

Everything the user cares about (role families, scoring weights, locations,
thresholds, the master CV) lives in ``config/profile.yaml`` and
``config/master_cv.yaml`` so it can be tuned without touching code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = REPO_ROOT / "config" / "profile.yaml"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "jobpilot.db"
BASE_URL = "https://api.adzuna.com/v1/api"


class ConfigError(Exception):
    """Raised when the YAML config is malformed or missing required keys."""


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader (no python-dotenv dependency).

    Values are only set when the variable is not already present in the
    environment, so real environment variables always win.
    """
    dotenv = path or REPO_ROOT / ".env"
    if not dotenv.exists():
        return
    for raw in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        os.environ.setdefault(key, value)


# --------------------------------------------------------------------------- #
# Search / sources
# --------------------------------------------------------------------------- #
@dataclass
class SearchLocation:
    name: str
    adzuna_country: str | None = None  # ISO-2 for Adzuna, e.g. es / de / gb


@dataclass
class SearchConfig:
    target_offers: int = 300
    max_results_per_query: int = 50
    max_pages_per_query: int = 2
    exclude_foreign_onsite: bool = True  # drop hybrid/on-site roles outside Spain
    locations: list[SearchLocation] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Role families
# --------------------------------------------------------------------------- #
@dataclass
class FamilyConfig:
    id: str
    label: str
    queries: list[str]
    sources: list[str]
    weight: float = 1.0
    interest: float = 10.0  # weight for the "interest" scoring dimension
    search_locations: list[str] = field(default_factory=list)  # names (subset of search.locations)
    skills: dict[str, float] = field(default_factory=dict)  # keyword -> score contribution
    seniority_hint: str = ""  # e.g. "junior"
    adzuna_queries: dict[str, list[str]] = field(default_factory=dict)  # ISO-2 country -> queries


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
@dataclass
class ScoringConfig:
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "skills": 30,
            "experience": 20,
            "education": 10,
            "location": 15,
            "seniority": 15,
            "interest": 10,
        }
    )
    threshold: float = 65.0  # >= threshold -> 🟢 apply
    review_threshold: float = 45.0  # >= review, < threshold -> 🟡 review
    min_skills_for_apply: float = 20.0  # skills-dim value required to reach apply


@dataclass
class LocationPref:
    area: str
    kind: str  # onsite | hybrid | remote
    weight: float = 50.0


@dataclass
class ProfileConfig:
    seniority_target: str = "junior"
    locations: list[LocationPref] = field(default_factory=list)
    languages: list[str] = field(default_factory=lambda: ["es", "en"])
    exclude_companies: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Master CV
# --------------------------------------------------------------------------- #
@dataclass
class MasterCV:
    contact: dict
    summary: str
    experience: list[dict]
    education: list[dict]
    skills: dict  # {"name": [items], ...} groups
    projects: list[dict] = field(default_factory=list)
    certifications: list[dict] = field(default_factory=list)

    def in_lang(self, lang: str, default: str = "es") -> MasterCV:
        """A copy with every narrative field resolved to ``lang``.

        Narrative values may be plain strings (language-neutral) or dicts like
        ``{es: ..., en: ...}``. Structural dicts/lists are walked recursively;
        skills and contact are never translated.
        """
        return MasterCV(
            contact=self.contact,
            summary=_pick_lang(self.summary, lang, default),
            experience=_pick_lang(self.experience, lang, default),
            education=_pick_lang(self.education, lang, default),
            skills=self.skills,
            projects=_pick_lang(self.projects, lang, default),
            certifications=_pick_lang(self.certifications, lang, default),
        )


def _pick_lang(value: Any, lang: str, default: str) -> Any:
    if isinstance(value, dict):
        if all(isinstance(k, str) and k.lower() in {"es", "en"} for k in value):
            return value.get(lang) or value.get(default) or next(iter(value.values()), "")
        return {k: _pick_lang(v, lang, default) for k, v in value.items()}
    if isinstance(value, list):
        return [_pick_lang(v, lang, default) for v in value]
    return value


# --------------------------------------------------------------------------- #
# Top level
# --------------------------------------------------------------------------- #
@dataclass
class Config:
    profile_path: Path
    db_path: Path
    snapshot_dir: Path
    master_cv: MasterCV
    search: SearchConfig
    families: list[FamilyConfig]
    scoring: ScoringConfig
    profile: ProfileConfig
    output_dir: Path = field(default_factory=lambda: Path("output"))
    ats_companies: dict[str, list[str]] = field(default_factory=dict)  # source -> [company slug]

    def family(self, family_id: str) -> FamilyConfig:
        for fam in self.families:
            if fam.id == family_id:
                return fam
        raise ConfigError(f"unknown family: {family_id!r}")

    def master(self, lang: str | None = None) -> MasterCV:
        """The master CV resolved to a language (default: profile.languages[0])."""
        default = self.profile.languages[0] if self.profile.languages else "es"
        return self.master_cv.in_lang(lang or default, default=default)

    @property
    def sources(self) -> list[str]:
        seen: list[str] = []
        for fam in self.families:
            for src in fam.sources:
                if src not in seen:
                    seen.append(src)
        return seen


def _require(mapping: dict, key: str, where: str) -> None:
    if key not in mapping:
        raise ConfigError(f"missing key {key!r} in {where}")


def parse_search(raw: dict) -> SearchConfig:
    locs = []
    for item in raw.get("locations", []):
        locs.append(
            SearchLocation(name=item["name"], adzuna_country=item.get("adzuna_country"))
        )
    return SearchConfig(
        target_offers=int(raw.get("target_offers", 300)),
        max_results_per_query=int(raw.get("max_results_per_query", 50)),
        max_pages_per_query=int(raw.get("max_pages_per_query", 2)),
        exclude_foreign_onsite=bool(raw.get("exclude_foreign_onsite", True)),
        locations=locs,
    )


def parse_families(raw: list) -> list[FamilyConfig]:
    families = []
    for item in raw:
        _require(item, "id", "families")
        _require(item, "queries", f"family {item['id']!r}")
        families.append(
            FamilyConfig(
                id=item["id"],
                label=item.get("label", item["id"]),
                queries=list(item["queries"]),
                sources=list(item.get("sources", [])),
                weight=float(item.get("weight", 1.0)),
                interest=float(item.get("interest", 10.0)),
                search_locations=list(item.get("search_locations", [])),
                skills={k: float(v) for k, v in (item.get("skills") or {}).items()},
                seniority_hint=item.get("seniority_hint", ""),
                adzuna_queries={
                    ccode: [str(q) for q in queries]
                    for ccode, queries in (item.get("adzuna_queries") or {}).items()
                },
            )
        )
    if not families:
        raise ConfigError("no families configured (add at least one entry)")
    return families


def parse_profile(raw: dict) -> ProfileConfig:
    prefs = [
        LocationPref(area=item["area"], kind=item.get("kind", "onsite"), weight=float(item.get("weight", 50)))
        for item in raw.get("locations", [])
    ]
    return ProfileConfig(
        seniority_target=raw.get("seniority_target", "junior"),
        locations=prefs,
        languages=list(raw.get("languages", ["es", "en"])),
        exclude_companies=list(raw.get("exclude_companies", [])),
    )


def parse_master_cv(path: Path) -> MasterCV:
    if not path.exists():
        raise ConfigError(f"master CV not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("contact", "summary", "experience", "education", "skills"):
        _require(raw, key, str(path))
    return MasterCV(
        contact=raw["contact"],
        summary=raw["summary"],
        experience=raw["experience"],
        education=raw["education"],
        skills=raw["skills"],
        projects=raw.get("projects", []),
        certifications=raw.get("certifications", []),
    )


def load_config(profile_path: Path = DEFAULT_PROFILE) -> Config:
    load_dotenv()
    if not profile_path.exists():
        raise ConfigError(
            f"profile not found: {profile_path}. Run `jobpilot init` to scaffold it."
        )
    raw = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    top = raw.get("project", {})
    search = raw.get("search", {}) or {}
    return Config(
        profile_path=profile_path,
        db_path=Path(top.get("db_path", str(DEFAULT_DB_PATH))),
        snapshot_dir=Path(top.get("snapshot_dir", str(REPO_ROOT / "data" / "snapshots"))),
        master_cv=parse_master_cv(Path(top.get("master_cv", "config/master_cv.yaml"))),
        search=parse_search(search),
        families=parse_families(raw.get("families", []) or []),
        scoring=ScoringConfig(
            weights={k: float(v) for k, v in (raw.get("scoring", {}).get("weights", {})).items()},
            threshold=float(raw.get("scoring", {}).get("threshold", 65.0)),
            review_threshold=float(raw.get("scoring", {}).get("review_threshold", 45.0)),
            min_skills_for_apply=float(raw.get("scoring", {}).get("min_skills_for_apply", 20.0)),
        ),
        profile=parse_profile(raw.get("profile", {}) or {}),
        output_dir=Path(top.get("output_dir", "output")),
        ats_companies={
            key: [str(c) for c in (raw.get("ats_companies", {}).get(key) or [])]
            for key in ("greenhouse", "lever")
        },
    )
