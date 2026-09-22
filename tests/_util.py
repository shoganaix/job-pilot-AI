"""Shared test helpers."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from jobpilot.config import SearchLocation
from jobpilot.models import Offer, SourcePage
from jobpilot.sources.base import JobSource

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    with (FIXTURES / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def temp_db_path(tmp_path) -> Path:
    return tmp_path / "jobpilot_test.db"


class FakeSource(JobSource):
    """Deterministic in-memory source for pipeline tests."""

    name = "fake"

    def __init__(self, offers: list[Offer] | None = None, **kw) -> None:
        super().__init__(**kw)
        self._offers = offers or []

    @staticmethod
    def locations() -> list[SearchLocation]:
        return [SearchLocation(name="Spain", adzuna_country="es")]

    def search(self, query, location, page=1, page_size=50) -> SourcePage:
        return SourcePage(
            offers=[copy.copy(off) for off in self._offers],
            has_more=False,
            total_found=len(self._offers),
        )
