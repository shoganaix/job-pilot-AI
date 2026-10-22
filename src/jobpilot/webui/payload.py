"""Turn submitted form fields (``parse_qs`` output) into YAML structures.

Pure functions, no HTTP and no filesystem: given a ``dict[str, list[str]]``
they build the dicts the YAML validators check. Keeping this separate from
``forms.py`` (HTML) and ``server.py`` (HTTP) is what makes it testable.
"""

from __future__ import annotations

import re
from typing import Any

from ..config import ConfigError

Form = dict[str, list[str]]

_ROW_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.(\d+)\.([A-Za-z0-9_]+)$")


def field(form: Form, name: str, default: str = "") -> str:
    values = form.get(name)
    return values[0] if values else default


def checked(form: Form, name: str) -> bool:
    return bool(form.get(name))


def checked_all(form: Form, name: str) -> list[str]:
    return list(form.get(name) or [])


def lines(form: Form, name: str) -> list[str]:
    """One list entry per non-blank line of a textarea."""
    return [ln.strip() for ln in field(form, name).splitlines() if ln.strip()]


def number(form: Form, name: str, default: float, kind: type = float) -> Any:
    raw = field(form, name).strip()
    if not raw:
        return default
    try:
        return kind(raw) if kind is int else float(raw)
    except ValueError:
        raise ConfigError(f"{name}: valor numérico inválido {raw!r}") from None


def rows(form: Form, prefix: str) -> list[tuple[int, dict[str, str]]]:
    """Collect ``prefix.<idx>.<field>`` inputs back into ordered rows.

    Indices may be sparse (the JS lets you delete any row) and are sorted
    ascending so saved order matches what the user sees.
    """
    buckets: dict[int, dict[str, str]] = {}
    for key, values in form.items():
        match = _ROW_RE.match(key)
        if not match or match.group(1) != prefix:
            continue
        buckets.setdefault(int(match.group(2)), {})[match.group(3)] = (
            values[0] if values else ""
        )
    return sorted(buckets.items())


def row_pairs(form: Form, prefix: str, fields: tuple[str, ...]) -> list[dict[str, str]]:
    """Like ``rows`` but skips rows where every listed field is blank."""
    out = []
    for _, data in rows(form, prefix):
        if any(data.get(f, "").strip() for f in fields):
            out.append({f: data.get(f, "") for f in fields})
    return out


def bilingual(es: str, en: str) -> list[dict[str, str]]:
    """Pair two textareas line-by-line, dropping lines blank on both sides."""
    es_lines = es.splitlines()
    en_lines = en.splitlines()
    pairs = []
    for i in range(max(len(es_lines), len(en_lines))):
        left = es_lines[i].strip() if i < len(es_lines) else ""
        right = en_lines[i].strip() if i < len(en_lines) else ""
        if left or right:
            pairs.append({"es": left, "en": right})
    return pairs


# --------------------------------------------------------------------------- #
# master_cv.yaml
# --------------------------------------------------------------------------- #
def build_master_cv(form: Form) -> dict[str, Any]:
    contact = {
        name: field(form, f"contact.{name}")
        for name in ("name", "email", "phone", "city", "linkedin", "github")
    }
    experience = []
    for row in row_pairs(
        form,
        "exp",
        ("company", "role_es", "role_en", "start", "end", "bullets_es", "bullets_en"),
    ):
        experience.append(
            {
                "company": row["company"].strip(),
                "role": {
                    "es": row["role_es"].strip(),
                    "en": row["role_en"].strip(),
                },
                "start": row["start"].strip(),
                "end": row["end"].strip(),
                "bullets": bilingual(row["bullets_es"], row["bullets_en"]),
            }
        )

    education = []
    for row in row_pairs(
        form, "edu", ("degree_es", "degree_en", "school", "start", "end")
    ):
        education.append(
            {
                "degree": {"es": row["degree_es"].strip(), "en": row["degree_en"].strip()},
                "school": row["school"].strip(),
                "start": row["start"].strip(),
                "end": row["end"].strip(),
            }
        )

    # skills are language-neutral: a plain dict {group: [item, ...]}
    skills: dict[str, list[str]] = {}
    for row in row_pairs(form, "sgrp", ("group", "items")):
        group = row["group"].strip()
        if group:
            skills[group] = [ln.strip() for ln in row["items"].splitlines() if ln.strip()]

    projects = []
    for row in row_pairs(
        form, "proj", ("name_es", "name_en", "url", "desc_es", "desc_en")
    ):
        projects.append(
            {
                "name": {"es": row["name_es"].strip(), "en": row["name_en"].strip()},
                "url": row["url"].strip(),
                "description": {
                    "es": row["desc_es"].strip(),
                    "en": row["desc_en"].strip(),
                },
            }
        )

    certifications = []
    for row in row_pairs(
        form, "cert", ("name_es", "name_en", "issuer", "year", "note_es", "note_en")
    ):
        certifications.append(
            {
                "name": {"es": row["name_es"].strip(), "en": row["name_en"].strip()},
                "issuer": row["issuer"].strip(),
                "year": row["year"].strip(),
                "note": {"es": row["note_es"].strip(), "en": row["note_en"].strip()},
            }
        )

    payload: dict[str, Any] = {
        "contact": contact,
        "summary": {"es": field(form, "summary.es"), "en": field(form, "summary.en")},
        "experience": experience,
        "education": education,
        "skills": skills,
    }
    if projects:
        payload["projects"] = projects
    if certifications:
        payload["certifications"] = certifications
    return payload


# --------------------------------------------------------------------------- #
# profile.yaml - search / profile / ats_companies
# --------------------------------------------------------------------------- #
def build_profile_patch(form: Form) -> dict[str, Any]:
    """Build the sections of profile.yaml owned by the preferences form."""
    search_locations = []
    for _, data in rows(form, "sloc"):
        name = data.get("name", "").strip()
        if name:
            search_locations.append(
                {"name": name, "adzuna_country": data.get("country", "").strip() or None}
            )

    profile_locations = []
    for _, data in rows(form, "ploc"):
        area = data.get("area", "").strip()
        if not area:
            continue
        raw_weight = data.get("weight") or "50"
        try:
            weight = float(raw_weight)
        except ValueError:
            raise ConfigError(
                f"ploc weight: valor numérico inválido {raw_weight!r}"
            ) from None
        profile_locations.append(
            {
                "area": area,
                "kind": data.get("kind", "onsite") or "onsite",
                "weight": weight,
            }
        )

    return {
        "search": {
            "target_offers": number(form, "search.target_offers", 300, int),
            "max_results_per_query": number(
                form, "search.max_results_per_query", 50, int
            ),
            "max_pages_per_query": number(form, "search.max_pages_per_query", 2, int),
            "exclude_foreign_onsite": checked(form, "search.exclude_foreign_onsite"),
            "exclude_seniority": checked_all(form, "search.exclude_seniority"),
            "locations": search_locations,
        },
        "profile": {
            "seniority_target": field(form, "profile.seniority_target", "junior"),
            "languages": [
                ln.strip()
                for ln in field(form, "profile.languages", "es, en").split(",")
                if ln.strip()
            ],
            "locations": profile_locations,
            "exclude_companies": lines(form, "profile.exclude_companies"),
        },
        "ats_companies": {
            "greenhouse": lines(form, "ats.greenhouse"),
            "lever": lines(form, "ats.lever"),
        },
    }


def apply_profile_patch(original: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Merge the form's sections into the loaded profile, keeping extra keys.

    ``project`` / ``scoring`` / anything else in the file pass through; the
    three edited sections are replaced wholesale (their structure is fully
    owned by the form).
    """
    merged = dict(original)
    merged.update(patch)
    return merged


# --------------------------------------------------------------------------- #
# profile.yaml - one family
# --------------------------------------------------------------------------- #
def build_family(form: Form, existing: dict[str, Any]) -> dict[str, Any]:
    """Update one family in place; ``existing`` supplies id and untouched keys."""
    fam_id = str(existing.get("id", ""))
    if not fam_id:
        raise ConfigError("family has no id")

    queries = lines(form, "family.queries")
    if not queries:
        raise ConfigError("la familia necesita al menos una query")
    sources = checked_all(form, "family.sources")
    if not sources:
        raise ConfigError("selecciona al menos una fuente")

    skills: dict[str, float] = {}
    for _, data in rows(form, "fskill"):
        name = data.get("name", "").strip()
        if not name:
            continue
        raw_weight = data.get("weight") or "1"
        try:
            weight = float(raw_weight)
        except ValueError:
            raise ConfigError(
                f"skill weight: valor numérico inválido {raw_weight!r}"
            ) from None
        skills[name] = weight

    fam = dict(existing)
    fam.update(
        {
            "label": field(form, "family.label", fam_id),
            "weight": number(form, "family.weight", 1.0),
            "interest": number(form, "family.interest", 10.0),
            "queries": queries,
            "sources": sources,
            "skills": skills,
        }
    )

    adzuna = {
        code: [ln for ln in field(form, f"family.adzuna.{code}").splitlines() if ln.strip()]
        for code in ("es", "de")
    }
    adzuna = {code: [ln.strip() for ln in v] for code, v in adzuna.items() if v}
    if adzuna:
        fam["adzuna_queries"] = adzuna
    else:
        fam.pop("adzuna_queries", None)

    hint = field(form, "family.seniority_hint").strip()
    if hint:
        fam["seniority_hint"] = hint
    else:
        fam.pop("seniority_hint", None)
    return fam
