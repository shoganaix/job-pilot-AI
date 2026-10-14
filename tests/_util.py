"""Shared test helpers."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml

from jobpilot.config import REPO_ROOT, Config, SearchLocation, load_config
from jobpilot.models import Offer, SourcePage
from jobpilot.sources.base import JobSource

FIXTURES = Path(__file__).parent / "fixtures"

# config/ is gitignored (personal data), so tests must never read the
# developer's real profile. These are the tracked scaffolds that `jobpilot
# init` writes, which keeps the suite deterministic on any clone.
SCAFFOLDS = REPO_ROOT / "src" / "jobpilot" / "resources"


def fixture(name: str):
    with (FIXTURES / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def temp_db_path(tmp_path) -> Path:
    return tmp_path / "jobpilot_test.db"


def sample_config(tmp_path) -> Config:
    """Load the scaffolded profile/master CV, redirected at a tmp workspace.

    Mirrors what ``jobpilot init`` produces on a fresh machine, but with the
    database, snapshots and output rooted in ``tmp_path`` so tests never touch
    the developer's real data/ and output/ directories.
    """
    master = tmp_path / "master_cv.yaml"
    master.write_text(
        (SCAFFOLDS / "master_cv.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    raw = yaml.safe_load((SCAFFOLDS / "profile.yaml").read_text(encoding="utf-8")) or {}
    raw["project"] = {
        "db_path": (tmp_path / "jobpilot.db").as_posix(),
        "snapshot_dir": (tmp_path / "snapshots").as_posix(),
        "master_cv": master.as_posix(),
        "output_dir": (tmp_path / "output").as_posix(),
    }
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return load_config(profile)


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
