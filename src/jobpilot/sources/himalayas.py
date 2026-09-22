"""Himalayas adapter.

Keyless remote-jobs API with deep, *structured* data (min/max salary, currency,
seniority, timezone, apply URL). Great for the scoring engine because the
fields it needs exist instead of having to be guessed from prose.

The API prefers cursor pagination (``nextCursor`` / ``?cursor=``; ``offset`` is
deprecated), so the adapter keeps per-(query, location) cursors and feeds them
across page calls.
"""

from __future__ import annotations

from typing import Any

from ..config import SearchLocation
from ..models import Offer, SourcePage
from .base import DEFAULT_USER_AGENT, JobSource, html_to_text, matches_query

API = "https://himalayas.app/jobs/api"


def _haystack(item: dict) -> str:
    return " ".join(
        [
            str(item.get("title", "")),
            str(item.get("companyName", "") or item.get("company", "")),
            " ".join(item.get("tags", []) or []),
            " ".join(item.get("categories", []) or []).replace("-", " "),
        ]
    )


class HimalayasSource(JobSource):
    name = "himalayas"
    remote_first = True
    scroll_feed = True

    def __init__(self, timeout: float = 30.0, user_agent: str = "") -> None:
        super().__init__(timeout=timeout, user_agent=user_agent or DEFAULT_USER_AGENT)
        self._cursors: dict[tuple[str, str], str | None] = {}

    def search(
        self,
        query: str,
        location: SearchLocation,
        page: int = 1,
        page_size: int = 100,
    ) -> SourcePage:
        key = (query, location.name)
        if page == 1 or key not in self._cursors:
            self._cursors[key] = None
        params: dict[str, Any] = {"limit": page_size}
        cursor = self._cursors.get(key)
        if cursor:
            params["cursor"] = cursor
        else:
            params["offset"] = (page - 1) * page_size
        payload = self._get_json(API, params=params)
        jobs = payload.get("jobs", [])
        next_cursor = payload.get("nextCursor") or None
        self._cursors[key] = next_cursor
        if not jobs:
            return SourcePage(offers=[], has_more=bool(next_cursor))
        matched = [item for item in jobs if matches_query(_haystack(item), query)]
        return SourcePage(offers=self.parse_offers(matched, query),
                          has_more=bool(next_cursor),
                          total_found=len(matched))

    def parse_offers(self, items: list[dict], query: str = "") -> list[Offer]:
        offers = []
        for item in items:
            smin = item.get("minSalary") if item.get("minSalary") is not None else item.get("salaryMin")
            smax = item.get("maxSalary") if item.get("maxSalary") is not None else item.get("salaryMax")
            currency = item.get("currency") or item.get("salaryCurrency") or ""
            salary_min = float(smin) if smin is not None else None
            salary_max = float(smax) if smax is not None else None
            seniority = item.get("seniority")
            if isinstance(seniority, list):
                seniority = ", ".join(str(x) for x in seniority) or None
            location = item.get("location") or ", ".join(item.get("locationRestrictions", []) or [])
            apply_url = item.get("applicationLink") or item.get("applyUrl") or item.get("url") or ""
            published_at = item.get("pubDate") or item.get("postedAt") or item.get("postedDatetime")
            offers.append(
                Offer(
                    source=self.name,
                    source_id=str(item.get("guid") or item.get("id", "")),
                    title=item.get("title", ""),
                    company=item.get("companyName") or item.get("company", ""),
                    location=location,
                    country=item.get("country", "") or "",
                    remote=True,
                    url=item.get("url", "") or apply_url,
                    apply_url=apply_url,
                    description=html_to_text(item.get("description", "")),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=currency,
                    seniority=str(seniority) if seniority else None,
                    published_at=str(published_at) if published_at else None,
                    tags=list(item.get("tags") or item.get("categories") or []),
                    query=query,
                    raw=item,
                )
            )
        return offers
