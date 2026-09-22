"""Core data models shared across JobPilot.

These types are source-agnostic: every source adapter normalizes its own
payloads into :class:`Offer`, and downstream logic (dedupe, matching, queue)
only ever sees these objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Triage(StrEnum):
    """Three-way triage produced by the matching engine."""

    APPLY = "apply"  # 🟢
    REVIEW = "review"  # 🟡
    DISCARD = "discard"  # 🔴


class AppStatus(StrEnum):
    """Lifecycle of an application in the queue."""

    NEW = "new"
    REVIEW = "review"
    APPLY = "apply"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    DISCARDED = "discarded"
    WITHDRAWN = "withdrawn"


@dataclass
class Offer:
    """A normalized job posting."""

    source: str
    source_id: str
    title: str
    company: str
    location: str = ""
    country: str | None = None
    remote: bool | None = None
    url: str = ""
    apply_url: str = ""
    description: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_text: str = ""
    currency: str = ""
    category: str = ""
    seniority: str | None = None
    published_at: str | None = None
    family: str = ""
    query: str = ""
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def description_length(self) -> int:
        return len(self.description)

    def short(self, width: int = 80) -> str:
        """Single-line-ish summary for CLI tables."""
        return f"[{self.source}] {self.company} — {self.title} ({self.location})"


@dataclass
class SourcePage:
    """The result of a single search request plus pagination state."""

    offers: list[Offer]
    has_more: bool = False
    total_found: int | None = None


@dataclass
class DimensionScore:
    """Per-dimension contribution to the final score (0-100 each)."""

    value: float  # 0-100
    weight: float  # configured weight (sums to 100 across dimensions)
    evidence: str = ""  # human-readable hint for the breakdown view


@dataclass
class Score:
    """Full matching result for one offer."""

    offer_id: int
    run_id: int
    total: float  # 0-100
    triage: Triage
    breakdown: dict[str, DimensionScore] = field(default_factory=dict)
    extracted: dict[str, Any] = field(default_factory=dict)  # what was extracted
    hard_filters: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class Application:
    """Row of the application queue."""

    offer_id: int
    status: AppStatus = AppStatus.NEW
    cv_variant: str = ""
    cv_file: str = ""
    notes: str = ""
    url: str = ""
    updated_at: str = ""


@dataclass
class Run:
    """A sync/score pipeline run, for audit & snapshots."""

    id: int | None = None
    started_at: str = ""
    notes: str = ""
    stats: dict[str, Any] = field(default_factory=dict)
