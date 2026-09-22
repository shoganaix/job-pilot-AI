"""Arbeitnow adapter.

Keyless European job feed (mostly Germany, but UE-wide and remote-first) with
full descriptions and a structured ``remote`` flag. The server-side ``search``
parameter loosely biases the feed towards the query (its results vary), so it
is requested per-query and then sieved locally with :func:`matches_query`.
Fetched pages are cached by ``(query, page)`` so repeated queries across
families don't re-download the same payload.
"""

from __future__ import annotations

from ..config import SearchLocation
from ..models import Offer, SourcePage
from .base import JobSource, html_to_text, matches_query

API = "https://www.arbeitnow.com/api/job-board-api"


def _haystack(item: dict) -> str:
    return " ".join(
        [
            str(item.get("title", "")),
            str(item.get("company_name", "")),
            " ".join(item.get("tags", []) or []),
            " ".join(item.get("job_types", []) or []),
        ]
    )


class ArbeitnowSource(JobSource):
    name = "arbeitnow"
    remote_first = True

    def __init__(self, timeout: float = 30.0, user_agent: str = "") -> None:
        super().__init__(timeout=timeout, user_agent=user_agent)
        self._page_cache: dict[tuple[str, int], dict] = {}

    def _fetch(self, query: str, page: int) -> dict:
        key = (query, page)
        if key not in self._page_cache:
            self._page_cache[key] = self._get_json(API, params={"page": page, "search": query})
        return self._page_cache[key]

    def search(
        self,
        query: str,
        location: SearchLocation,
        page: int = 1,
        page_size: int = 50,  # feed pages are fixed server-side; kept for interface parity
    ) -> SourcePage:
        payload = self._fetch(query, page)
        items = payload.get("data", [])
        kept = [item for item in items if matches_query(_haystack(item), query)]
        offers = self.parse_offers(kept, query)
        has_more = bool(items) and bool(payload.get("links", {}).get("next"))
        return SourcePage(offers=offers, has_more=has_more, total_found=len(kept))

    def parse_offers(self, items: list, query: str = "") -> list[Offer]:
        offers = []
        for item in items:
            salary_min, salary_max, salary_text = None, None, ""
            if item.get("salary"):
                salary_text = str(item["salary"])
                parts = [p.strip() for p in salary_text.replace("k", "000").split("-") if p.strip()]
                try:
                    if parts:
                        salary_min = float(parts[0].replace(".", "").replace(",", "").strip("€ $£"))
                    if len(parts) > 1:
                        salary_max = float(parts[1].replace(".", "").replace(",", "").strip("€ $£"))
                except ValueError:
                    salary_min = salary_max = None
            offers.append(
                Offer(
                    source=self.name,
                    source_id=str(item.get("slug", "")),
                    title=item.get("title", ""),
                    company=item.get("company_name", ""),
                    location=item.get("location", ""),
                    remote=bool(item.get("remote")),
                    url=item.get("url", ""),
                    apply_url=item.get("url", ""),
                    description=html_to_text(item.get("description", "")),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_text=salary_text,
                    category=", ".join(item.get("job_types", [])),
                    published_at=str(item.get("created_at", "")) if item.get("created_at") else None,
                    tags=list(item.get("tags", []) or []),
                    query=query,
                    raw=item,
                )
            )
        return offers
