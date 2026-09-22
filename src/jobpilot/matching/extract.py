"""Extract structured, scoreable signals from a raw Offer.

Everything here is deterministic regex/dict work — no LLM required. The result
feeds the six scoring dimensions and the hard-rule filters. ``skills`` maps a
canonical skill name (from the profile family) to the weight found in the
offer's text (title, tags, category and description).

Offers from structured sources (himalayas ``seniority``, ``minSalary``...)
are preferred over text guessing whenever the fields exist.
"""

from __future__ import annotations

import re
from typing import Any

from ..config import Config, ProfileConfig
from ..models import Offer
from .taxonomy import skill_aliases

EU_COUNTRIES = {
    "spain": "es", "germany": "de", "france": "fr", "italy": "it",
    "portugal": "pt", "netherlands": "nl", "belgium": "be", "ireland": "ie",
    "poland": "pl", "sweden": "se", "denmark": "dk", "finland": "fi",
    "austria": "at", "switzerland": "ch", "norway": "no", "czech": "cz",
    "czechia": "cz", "luxembourg": "lu", "greece": "gr",
    "hungary": "hu",
}

_SENIORITY_PATTERNS = [
    (r"\b(entry[- ]?level|fresh grad|new grad|junior|júnior|graduate|estudiante|becario|intern)\b", "junior"),
    (r"\b(mid[- ]?level|medior|intermediate|2\+|3\+)\b", "midlevel"),
    (r"\b(senior|sr\.|sr |advanced)\b", "senior"),
    (r"\b(lead|staff|principal)\b", "lead"),
]

_YEARS_RE = re.compile(
    r"(\d{1,2})\s*\+\s*(?:years|yrs|años|anos)|"
    r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s*(?:years|yrs|años|anos)|"
    r"(\d{1,2})\s*(?:years|yrs|años|anos)"
)

_EDUCATION_RE = [
    (r"\bmaster(?:'s|s)?\b|\bmsc\b|\bms\b(?!\w)", "master"),
    (r"\bbachelor(?:'s|s)?\b|\bbsc\b|\bbs\b(?!\w)", "bachelor"),
    (r"\bphd\b|doctorate|doctoral", "phd"),
]

_HARD_FILTER_RE = [
    ("US citizenship required", r"\b(u\.?s\.? citizen|citizenship required|green card holder|authorized to work in the (u\.?s\.?|united states))\b"),
    ("Security clearance required", r"\b((active|current|top[ -]?secret|do[ -]?d|ts/sci|polygraph)\s*(security|clearance)|security clearance)\b"),
    ("Located in the US only", r"\bmust (be (located|based)|currently reside)[^.]*\b(united states|usa|u\.?s\.?)\b"),
]


def _text(offer: Offer) -> str:
    parts = [offer.title, offer.company, offer.category, " ".join(offer.tags or [])]
    if offer.description:
        parts.append(offer.description)
    return " ".join(str(p) for p in parts if p)


def extract_skills(offer: Offer, skills: dict[str, float]) -> dict[str, float]:
    """Map of family skill -> weight, for skills present in the offer text.

    Multi-word skills are matched as phrases (spaces/hyphens intact); single
    tokens are matched exactly against the offer's word set, never by substring.
    """
    from .taxonomy import skill_tokens

    text = _text(offer).lower()
    words = set(re.findall(r"[a-z0-9#+.]+", text))
    found: dict[str, float] = {}
    for name, weight in skills.items():
        phrases = skill_aliases(name)
        tokens = skill_tokens(name)
        if (tokens & words) or any(p in text for p in phrases):
            found[name] = weight
    return found


def extract_seniority(offer: Offer) -> str | None:
    if offer.seniority:
        val = offer.seniority.lower()
        if "senior" in val:
            return "senior"
        if "lead" in val or "principal" in val or "staff" in val:
            return "lead"
        if "junior" in val or "entry" in val or "graduate" in val:
            return "junior"
        if "mid" in val:
            return "midlevel"
    text = _text(offer).lower()
    for pattern, level in _SENIORITY_PATTERNS:
        if re.search(pattern, text):
            return level
    return None


def extract_experience_years(offer: Offer) -> int | None:
    text = _text(offer).lower()
    m = _YEARS_RE.search(text)
    if not m:
        return None
    lo = m.group(1) or m.group(2)
    hi = m.group(3)
    try:
        if lo and hi:
            return (int(lo) + int(hi)) // 2
        return int(lo)
    except (TypeError, ValueError):
        return None


def extract_education(offer: Offer) -> str | None:
    """Highest degree level mentioned as required: phd > master > bachelor."""
    text = _text(offer).lower()
    for pattern, level in _EDUCATION_RE:
        if re.search(pattern, text):
            return level
    return None


def extract_location(offer: Offer, profile: ProfileConfig) -> dict[str, Any]:
    """Resolve the offer's location to the best matching profile preference."""
    loc = (offer.location or "").lower()
    words = set(re.findall(r"[a-záéíóúñü]+", loc))
    eu_codes = set(EU_COUNTRIES.values())
    country = (offer.country or "").lower()

    if is_remote_offer(offer):
        eu = (country in eu_codes) or bool(words & set(EU_COUNTRIES))
        area = "Remote EU" if eu else "Remote global"
        weight = _pref_weight(profile, "remote", area.lower(), 90.0 if eu else 60.0)
        kind = "remote"
    elif is_spain_offer(offer):
        area = "Spain"
        weight = _pref_weight(profile, "onsite", "spain", 85.0)
        kind = "onsite"
    else:
        area = "Foreign"
        weight = 20.0
        kind = "onsite"

    return {
        "area": area,
        "kind": kind,
        "weight": weight,
        "remote": kind == "remote",
        "onsite": kind == "onsite",
    }


_ACCENTS = str.maketrans({"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u"})


def _plain(text: str) -> str:
    return (text or "").lower().translate(_ACCENTS)


# Spanish city/region hints (accent-insensitive) so on-site Spanish postings are
# recognized even when Adzuna writes them fully in Spanish ("España, Cataluña...").
_SPAIN_HINTS = (
    "espa", "spain", "madrid", "barcelona", "valencia", "zaragoza", "bilbao",
    "sevilla", "malaga", "galicia", "catalu", "andaluc", "asturias", "canaria",
    "girona", "vizcaya", "vasc", "granada", "murcia", "palma", "tenerife",
)

# Explicit "remote for sure" markers scanned in location+description (helps
# German/UK postings like "100 % Home-Office"). "Híbrido"/"hybrid" is NOT enough.
_REMOTE_FULL_RE = re.compile(r"100\s*%\s*home[-\s]?office|100\s*%\s*remote|fully (remote|home[-\s]?office)")


def is_remote_offer(offer: Offer) -> bool:
    """True when the posting is (explicitly) fully remote."""
    loc = (offer.location or "").lower()
    words = set(re.findall(r"[a-záéíóúñü]+", loc))
    if "remote" in words or "anywhere" in words or "work from anywhere" in loc:
        return True
    # Trust the structured flag, except remoteok sets it on everything.
    if bool(offer.remote) and offer.source != "remoteok":
        return True
    return bool(_REMOTE_FULL_RE.search(_plain(loc + " " + _text(offer))))


def is_spain_offer(offer: Offer) -> bool:
    loc = _plain(offer.location or "")
    if "port of" in loc:  # Port of Spain, Trinidad is NOT Spain
        return False
    return any(hint in loc for hint in _SPAIN_HINTS)


def foreign_relocation_reason(offer: Offer) -> str | None:
    """Reason to drop a posting the user cannot attend in person.

    Keep 100 % remote offers anywhere and any posting in Spain; exclude foreign
    hybrid/on-site roles (the user cannot relocate).
    """
    if is_remote_offer(offer) or is_spain_offer(offer):
        return None
    return "no es 100% remoto y no está en España"


def _pref_weight(profile: ProfileConfig, kind: str, contains: str, default: float) -> float:
    vals = [p.weight for p in profile.locations if p.kind == kind and contains in p.area.lower()]
    return max(vals) if vals else default


def extract_hard_filters(offer: Offer, config: Config) -> list[str]:
    text = _text(offer).lower()
    reasons: list[str] = []
    for reason, pattern in _HARD_FILTER_RE:
        if pattern and re.search(pattern, text):
            reasons.append(reason)
    company = (offer.company or "").strip().lower()
    excluded = {c.strip().lower() for c in config.profile.exclude_companies}
    if company in excluded:
        reasons.append("Excluded company")
    return reasons


def extract_offer_signals(offer: Offer, family, config: Config) -> dict[str, Any]:
    """All structured signals for one offer against one family."""
    return {
        "skills": extract_skills(offer, family.skills),
        "seniority": extract_seniority(offer),
        "experience_years": extract_experience_years(offer),
        "education": extract_education(offer),
        "location": extract_location(offer, config.profile),
    }
