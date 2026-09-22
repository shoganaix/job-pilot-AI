"""RemoteOK adapter.

Keyless global remote-tech feed. The whole board is returned per call (first
element is a legal notice), so we fetch it once per adapter instance and filter
client-side per query.
"""

from __future__ import annotations

from ..config import SearchLocation
from ..models import Offer, SourcePage
from .base import JobSource, html_to_text

API = "https://remoteok.com/api"


class RemoteOKSource(JobSource):
    name = "remoteok"
    remote_first = True

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self._feed: list[dict] | None = None

    def _fetch_feed(self) -> list[dict]:
        if self._feed is None:
            raw = self._get_json(API)
            # element 0 is a legal notice (dict), not a job
            self._feed = [item for item in raw if isinstance(item, dict) and item.get("id")]
        return self._feed

    def search(
        self,
        query: str,
        location: SearchLocation,
        page: int = 1,
        page_size: int = 50,
    ) -> SourcePage:
        all_jobs = self._fetch_feed()
        tokens = [t for t in query.lower().replace("-", " ").split() if len(t) > 2]
        matched = [
            item for item in all_jobs
            if self._matches(item, tokens)
        ]
        offers = self.parse_offers(matched, query)
        start = (page - 1) * page_size
        window = offers[start:start + page_size]
        has_more = (start + page_size) < len(offers)
        return SourcePage(offers=window, has_more=has_more, total_found=len(offers))

    @staticmethod
    def _matches(item: dict, tokens: list[str]) -> bool:
        haystack = " ".join(
            [str(item.get("position", "")), str(item.get("company", "")), " ".join(item.get("tags", []) or [])]
        ).lower()
        return all(tok in haystack for tok in tokens)

    def parse_offers(self, items: list[dict], query: str = "") -> list[Offer]:
        offers = []
        for item in items:
            offers.append(
                Offer(
                    source=self.name,
                    source_id=str(item.get("id", "")),
                    title=item.get("position", ""),
                    company=item.get("company", ""),
                    location=item.get("location") or "Remote",
                    remote=True,
                    url="https://remoteok.com" + (item.get("url", "") or ""),
                    apply_url="https://remoteok.com" + (item.get("apply_url", "") or ""),
                    description=html_to_text(item.get("description", "")),
                    salary_min=item.get("salary_min") or None,
                    salary_max=item.get("salary_max") or None,
                    salary_text=str(item.get("salary_range", "")) if item.get("salary_range") else "",
                    published_at=str(item.get("date", "")) if item.get("date") else None,
                    tags=list(item.get("tags", []) or []),
                    query=query,
                    raw=item,
                )
            )
        return offers
