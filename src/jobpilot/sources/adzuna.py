"""Adzuna adapter.

Free API (app_id/app_key after registering) with the best free coverage of
Spain and other EU countries. Descriptions come back as short excerpts, so fine
for title/category/salary matching, but the deep scoring is better served by
the keyless remote sources which carry full descriptions.
"""

from __future__ import annotations

import os

from ..config import SearchLocation
from ..models import Offer, SourcePage
from .base import JobSource, SourceUnavailable, html_to_text

API = "https://api.adzuna.com/v1/api"

# Adzuna returns very broad "category.label" values; the free feed mixes in
# non-engineering sectors (hospitality, sales, admin, ...). Drop those at
# ingestion so the corpus stays signal-rich. Matching is done on the lowercase
# label; the tech-ish sectors (Engineering, IT, Techniker, QA/Wissenschaft,
# Manufacturing, Graduate, Energy) are kept.
_NON_TECH_CATEGORIES = frozenset({
    "admin jobs", "administraci",
    "atención al cliente", "customer services",
    "limpieza", "cleaning", "cleaning jobs",
    "gastronom", "restauraci", "hotel", "hospitality & catering",
    "maintenance jobs", "wartung",
    "sales jobs", "ventas",
    "hr & recruitment", "recursos humanos", "personal & personal", "verwaltungsstellen",
    "buchhaltung", "finanzwesen", "accounting", "finance",
    "jurist", "legal",
    "logistics", "logistik", "lagerhalt", "almacén", "warehouse",
    "marketing", "publicidad", "pr, advertising",
    "nursing", "pflege", "healthcare", "gesundheitswesen",
    "teaching", "social work", "sozial",
    "trade & construction", "handel & bau",
    "sonstige/allgemeine", "otros trabajos", "part time jobs",
    "kreation & design", "creación & design",
})


class AdzunaSource(JobSource):
    name = "adzuna"
    requires_key = True

    def __init__(self, app_id: str | None = None, app_key: str | None = None, **kw) -> None:
        super().__init__(**kw)
        self.app_id = app_id or os.environ.get("ADZUNA_APP_ID", "")
        self.app_key = app_key or os.environ.get("ADZUNA_APP_KEY", "")
        if not (self.app_id and self.app_key):
            raise SourceUnavailable(
                "Adzuna needs ADZUNA_APP_ID/ADZUNA_APP_KEY (free at developer.adzuna.com). "
                "Add them to .env — or use the keyless sources (arbeitnow, remoteok, himalayas)."
            )

    @staticmethod
    def locations() -> list[SearchLocation]:
        return []  # country list is decided by the pipeline from config

    def search(
        self,
        query: str,
        location: SearchLocation,
        page: int = 1,
        page_size: int = 50,
    ) -> SourcePage:
        country = location.adzuna_country or "es"
        url = f"{API}/jobs/{country}/search/{page}"
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": query,
            "results_per_page": min(page_size, 50),
            "max_days_old": 21,
            "full_time": 1,
            "content-type": "application/json",
        }
        payload = self._get_json(url, params=params)
        offers = self.parse_offers(payload.get("results", []))
        for offer in offers:
            offer.family = offer.family or "general"
        total = payload.get("count")
        has_more = bool(offers) and (total or 0) > page * (payload.get("results_per_page", page_size) or page_size)
        return SourcePage(offers=offers, has_more=has_more, total_found=total)

    def parse_offers(self, raw: list) -> list[Offer]:
        offers = []
        for item in raw:
            category = (item.get("category") or {}).get("label", "") if isinstance(item.get("category"), dict) else ""
            if any(block in category.lower() for block in _NON_TECH_CATEGORIES):
                continue
            raw_min = item.get("salary_min")
            raw_max = item.get("salary_max")
            salary_min = float(raw_min) if isinstance(raw_min, (int, float)) else None
            salary_max = float(raw_max) if isinstance(raw_max, (int, float)) else None
            location_parts = item.get("location", {})
            area = location_parts.get("area") or []
            location_str = ", ".join(part for part in area if isinstance(part, str))
            offers.append(
                Offer(
                    source=self.name,
                    source_id=str(item.get("id", "")),
                    title=item.get("title", "") or "",
                    company=(item.get("company") or {}).get("display_name", "") if isinstance(item.get("company"), dict) else str(item.get("company", "")),
                    location=location_str,
                    country=location_parts.get("country", "") or None,
                    url=item.get("redirect_url", "") or "",
                    apply_url=item.get("redirect_url", "") or "",
                    description=html_to_text(item.get("description", "")),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_text=str(item.get("salary_min", "") or "") + (" - " + str(item.get("salary_max", "")) if item.get("salary_max") else ""),
                    category=(item.get("category") or {}).get("label", "") if isinstance(item.get("category"), dict) else "",
                    published_at=str(item.get("created", "")) if item.get("created") else None,
                    tags=[],
                    raw=item,
                )
            )
        return offers
