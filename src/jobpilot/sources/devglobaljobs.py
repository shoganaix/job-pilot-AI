"""Dev Global Jobs adapter (keyless, public JSON feed).

The board aggregates public ATS boards (Greenhouse, Lever, Ashby...) from large
tech companies, which is a lot of coverage for a single static feed: a user with
an empty ``ats_companies`` list gets big-tech postings without configuring one
company at a time.

Only the advertised feed is used (``/feeds/jobs/latest.json``): the paginated
``/api/v1/jobs`` endpoint is disallowed in the site's robots.txt. The feed
exposes the 30 newest postings, so this is a trickle caught by frequent syncs
rather than a board you can sweep; the pipeline dedupes the overlap against the
direct ATS sources via ``dedupe_hash``.
"""

from __future__ import annotations

import re
from typing import Any

from ..config import SearchLocation
from ..models import Offer, SourcePage
from .base import DEFAULT_USER_AGENT, JobSource, html_to_text

FEED = "https://devglobaljobs.com/feeds/jobs/latest.json"

_REMOTE_RE = re.compile(r"\b(remote|distributed|anywhere|global)\b", re.IGNORECASE)


class DevGlobalJobsSource(JobSource):
    name = "devglobaljobs"
    scroll_feed = True

    def __init__(self, timeout: float = 30.0, user_agent: str = "") -> None:
        super().__init__(timeout=timeout, user_agent=user_agent or DEFAULT_USER_AGENT)
        self._feed: list[dict] = []

    def _fetch_feed(self) -> list[dict]:
        """The whole feed, downloaded once per instance."""
        if not self._feed:
            payload = self._get_json(FEED)
            items = payload.get("items", []) if isinstance(payload, dict) else []
            self._feed = [item for item in items if isinstance(item, dict)]
        return self._feed

    def search(
        self,
        query: str,
        location: SearchLocation,
        page: int = 1,
        page_size: int = 50,
    ) -> SourcePage:
        items = self._fetch_feed()
        start = max(page - 1, 0) * max(page_size, 1)
        window = items[start : start + max(page_size, 1)]
        return SourcePage(
            offers=self.parse_offers(window),
            has_more=start + len(window) < len(items),
            total_found=len(items),
        )

    def parse_offers(self, raw: Any) -> list[Offer]:
        offers = []
        for item in raw or []:
            source_id = str(item.get("id", "") or "")
            title = str(item.get("title", "") or "")
            company = str(item.get("organization", "") or "")
            if not source_id or not title or not company:
                continue
            location = str(item.get("location", "") or "")
            canonical = str(item.get("canonical_url", "") or "")
            apply_url = str(item.get("source_url", "") or "") or canonical
            offers.append(
                Offer(
                    source=self.name,
                    source_id=source_id,
                    title=title,
                    company=company,
                    location=location,
                    country=str(item.get("country", "") or "") or None,
                    remote=bool(_REMOTE_RE.search(location)),
                    url=canonical or apply_url,
                    apply_url=apply_url,
                    description=html_to_text(item.get("description", "")),
                    salary_text=str(item.get("salary", "") or ""),
                    category=str(item.get("skill_category", "") or ""),
                    published_at=str(item.get("date_posted", "")) or None,
                    query="",
                    raw=item,
                )
            )
        return offers
