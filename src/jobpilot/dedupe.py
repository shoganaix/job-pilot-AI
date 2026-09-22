"""Multi-source de-duplication.

Different boards publish the same role (or nearly identical ones). We compute a
stable fingerprint from normalized title + company + location so a single job
is stored once no matter how many sources/queries surface it.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from .models import Offer

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize(text: str | None) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("&", " and ")
    return " ".join(_TOKEN_RE.findall(text))


def compute_dedupe_hash(offer: Offer) -> str:
    """Fingerprint for one offer, stable across sources.

    When a source is authoritative about its own id (e.g. Adzuna), the source
    id is still part of uniqueness at the storage layer, but the fingerprint is
    what collapses duplicates *across* sources, so we deliberately ignore raw
    ids here.
    """
    parts = [normalize(offer.title), normalize(offer.company), normalize(offer.location)]
    key = "|".join(parts)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def batch_dedupe(offers: list[Offer]) -> tuple[list[Offer], list[Offer]]:
    """Split a batch into (unique, duplicated).

    Keeps the first occurrence per fingerprint; duplicates are returned
    separately so callers can log/track them.
    """
    seen: dict[str, Offer] = {}
    unique: list[Offer] = []
    dupes: list[Offer] = []
    for offer in offers:
        h = compute_dedupe_hash(offer)
        if h in seen:
            dupes.append(offer)
        else:
            seen[h] = offer
            unique.append(offer)
    return unique, dupes
