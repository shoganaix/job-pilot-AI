"""Score pipeline: run the matching engine over stored offers and persist scores."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .. import storage as store
from ..config import Config
from ..matching.scoring import score_offer
from ..models import DimensionScore, Offer, Score, Triage
from .search import guess_family


@dataclass
class ScoreStats:
    scored: int = 0
    by_triage: dict[str, int] = field(default_factory=lambda: {t: 0 for t in Triage})
    total: float = 0.0
    discarded_by_hard_filters: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "scored": self.scored,
            "by_triage": dict(self.by_triage),
            "avg": round(self.total / self.scored, 1) if self.scored else 0.0,
            "discarded_by_hard_filters": self.discarded_by_hard_filters,
        }


def offer_from_row(row) -> Offer:
    """Materialize an Offer from an offers DB row for scoring."""
    return Offer(
        source=str(row["source"]),
        source_id=str(row["source_id"]),
        title=str(row["title"]),
        company=str(row["company"]),
        location=str(row["location"] or ""),
        country=row["country"],
        remote=bool(row["remote"]),
        url=str(row["url"] or ""),
        apply_url=str(row["apply_url"] or ""),
        description=str(row["description"] or ""),
        salary_min=row["salary_min"],
        salary_max=row["salary_max"],
        salary_text=str(row["salary_text"] or ""),
        currency=str(row["currency"] or ""),
        category=str(row["category"] or ""),
        seniority=str(row["seniority"] or "") if row["seniority"] else None,
        published_at=str(row["published_at"] or "") if row["published_at"] else None,
        family=str(row["family"] or ""),
        tags=[],
    )


def pick_family(config: Config, offer: Offer, family_filter: str | None) -> str:
    """Choose the family to score against (explicit, queried filter, or guessed)."""
    offered = (offer.family or "").strip()
    if family_filter:
        return family_filter
    for candidate in [f for f in offered.split(",") if f]:
        try:
            config.family(candidate)
            return candidate
        except Exception:
            continue
    return guess_family(config, offer, "general")


def run_score(
    config: Config,
    conn,
    *,
    run=None,
    family_filter: str | None = None,
    limit: int | None = None,
    sleep_s: float = 0.0,
) -> ScoreStats:
    """Score all unscores/matching offers and persist results."""
    stats = ScoreStats()
    run_id = run.id if run else None
    rows = store.list_offers(conn, families=[family_filter] if family_filter else None, limit=limit)
    if not rows:
        return stats

    for row in rows:
        offer = offer_from_row(row)
        family_id = pick_family(config, offer, family_filter)
        try:
            family = config.family(family_id)
        except Exception:
            continue
        result = score_offer(offer, family, config)
        triage = result["triage"]
        score = Score(
            offer_id=row["id"],
            run_id=run_id or -1,
            total=result["total"],
            triage=triage,
            breakdown={
                name: DimensionScore(
                    value=d["value"], weight=d["weight"], evidence=d["evidence"]
                )
                for name, d in result["breakdown"].items()
            },
            extracted=result["extracted"],
            hard_filters=result["hard_filters"],
            reason=result["reason"],
        )
        if run_id:
            store.save_scores(conn, run_id, [score])
        stats.scored += 1
        stats.by_triage[triage.value] = stats.by_triage.get(triage.value, 0) + 1
        stats.total += score.total
        if result["hard_filters"]:
            stats.discarded_by_hard_filters += 1
        if sleep_s:
            time.sleep(sleep_s)
    return stats
