"""Target-company ATS boards (Greenhouse, Lever).

These don't provide keyless *search* — instead each target company exposes its
whole board. Useful for a watchlist of robotics/space employers: can't get a
100-job feed cheaply anywhere else, and the apply URLs are direct ATS links
that play perfectly with the Rezi extension.
"""

from __future__ import annotations

from ..config import SearchLocation
from ..models import Offer, SourcePage
from .base import JobSource, html_to_text

GREENHOUSE_LIST = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
LEVER_POSTINGS = "https://api.lever.co/v0/postings/{company}"


class GreenhouseSource(JobSource):
    name = "greenhouse"

    def __init__(self, companies: list[str], **kw) -> None:
        super().__init__(**kw)
        self.companies = companies

    def search(
        self,
        query: str,  # treated as the company slug when this adapter is driven company-by-company
        location: SearchLocation,
        page: int = 1,
        page_size: int = 100,
    ) -> SourcePage:
        company = query
        payload = self._get_json(
            GREENHOUSE_LIST.format(company=company),
            params={"content": "true", "page": max(page, 1), "per_page": page_size},
        )
        jobs = payload.get("jobs", [])
        offers = [self._to_offer(job, company) for job in jobs]
        total = payload.get("meta", {}).get("total")
        has_more = bool(jobs) and (total or 0) > page * page_size
        return SourcePage(offers=offers, has_more=has_more, total_found=total)

    def _to_offer(self, job: dict, company: str) -> Offer:
        location = (job.get("location") or {})
        return Offer(
            source=self.name,
            source_id=str(job.get("id", "")),
            title=job.get("title", ""),
            company=job.get("company_name") or company,
            location=location.get("name", ""),
            country=location.get("country", "") or None,
            remote=False,
            url=job.get("absolute_url", ""),
            apply_url=job.get("absolute_url", ""),
            description=html_to_text(job.get("content", "")),
            category=job.get("department", ""),
            published_at=job.get("updated_at") or job.get("first_published", ""),
            raw=job,
        )


class LeverSource(JobSource):
    name = "lever"

    def __init__(self, companies: list[str], **kw) -> None:
        super().__init__(**kw)
        self.companies = companies

    def search(
        self,
        query: str,  # company slug
        location: SearchLocation,
        page: int = 1,
        page_size: int = 200,
    ) -> SourcePage:
        postings = self._get_json(LEVER_POSTINGS.format(company=query))
        if isinstance(postings, dict):
            postings = postings.get("data", []) or []
        all_offers = [self._to_offer(item, query) for item in postings]
        start = (page - 1) * page_size
        window = all_offers[start:start + page_size]
        return SourcePage(offers=window, has_more=(start + page_size) < len(all_offers), total_found=len(all_offers))

    def _to_offer(self, item: dict, company: str) -> Offer:
        categories = item.get("categories") or {}
        location = categories.get("allLocations") or [categories.get("location", "")]
        if isinstance(location, list):
            location = ", ".join(str(x) for x in location if x)
        salary_min, salary_max = None, None
        salary = item.get("salaryRange") or {}
        if salary:
            try:
                salary_min = float(salary.get("min")) if salary.get("min") is not None else None
                salary_max = float(salary.get("max")) if salary.get("max") is not None else None
            except (TypeError, ValueError):
                salary_min = salary_max = None
        return Offer(
            source=self.name,
            source_id=str(item.get("id", "")),
            title=item.get("text", ""),
            company=str(item.get("company", company)),
            location=str(location),
            remote=any(True for wp in [str(item.get("workplaceType", ""))] if wp.lower() == "remote"),
            url=item.get("hostedUrl", ""),
            apply_url=item.get("hostedUrl", ""),
            description=html_to_text(item.get("descriptionPlain", "") or item.get("description", "")),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_text=str(salary) if salary else "",
            category=categories.get("team", ""),
            published_at=str(item.get("createdAt", "")) if item.get("createdAt") else None,
            tags=categories.get("commitment", []),
            raw=item,
        )
