"""Search pipeline: plan, run and record multi-source job searches.

Executes every (family, query, source, location) pair in the profile,
pagination-aware, politeness-limited, and persists normalized offers plus raw
snapshots to SQLite / disk so runs are reproducible and auditable.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from .. import storage as store
from ..config import Config, FamilyConfig, SearchLocation
from ..models import Run, SourcePage
from ..sources.base import JobSource, SourceError, SourceUnavailable, matches_query


@dataclass
class PlannedQuery:
    family: FamilyConfig
    source: str
    location: SearchLocation
    query: str

    @property
    def queries(self) -> list[str]:
        """Queries to run for this slot: country-localized for Adzuna when the
        profile provides them (e.g. Spanish terms for Spain), else the base set."""
        if self.source == "adzuna" and self.location.adzuna_country:
            localized = self.family.adzuna_queries.get(self.location.adzuna_country)
            if localized:
                return localized
        return self.family.queries


@dataclass
class SyncStats:
    calls: dict[str, int] = field(default_factory=dict)  # source -> http calls
    raw_rows: dict[str, int] = field(default_factory=dict)  # source -> offers fetched
    stored: dict[str, list[int]] = field(default_factory=dict)  # source -> [inserted, updated, dupes]
    seen_by_family: dict[str, int] = field(default_factory=dict)  # family -> offers seen
    disabled: dict[str, str] = field(default_factory=dict)
    total_inserted: int = 0
    total_updated: int = 0
    total_dupes: int = 0
    total_stored: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "raw_rows": self.raw_rows,
            "stored": {k: v for k, v in self.stored.items()},
            "seen_by_family": self.seen_by_family,
            "disabled": self.disabled,
            "total_inserted": self.total_inserted,
            "total_updated": self.total_updated,
            "total_dupes": self.total_dupes,
            "total_stored": self.total_stored,
        }


def resolve_locations(source: JobSource, config: Config, family: FamilyConfig) -> list[SearchLocation]:
    """Locations a given source should be queried for."""
    cands = source.locations()
    if not cands:  # Adzuna-style: countries come from the profile
        cands = [loc for loc in config.search.locations if loc.adzuna_country]
    if family.search_locations:
        names = set(family.search_locations)
        cands = [loc for loc in cands if loc.name in names]
    return cands or [SearchLocation(name="Remote", adzuna_country=None)]


def plan(config: Config, sources: dict[str, JobSource]) -> list[PlannedQuery]:
    """Enumerate every query request the run will make (excluding ATS pass)."""
    planned: list[PlannedQuery] = []
    for family in config.families:
        for src_name in family.sources:
            if src_name in ("greenhouse", "lever"):
                continue  # handled by the targeted ATS pass
            if src_name not in sources:
                continue
            src = sources[src_name]
            for location in resolve_locations(src, config, family):
                slot = PlannedQuery(family=family, source=src_name, location=location, query="")
                for query in slot.queries:
                    planned.append(replace(slot, query=query))
    return planned


def guess_family(config: Config, offer, fallback: str = "general") -> str:
    """Best-matching family by title overlap with the family queries."""
    title = offer.title.lower()
    best, best_score = fallback, 0.0
    for family in config.families:
        score = sum(1 for q in family.queries if matches_query(title, q))
        if score > best_score:
            best, best_score = family.id, score
    return best


# Scroll feeds that ignore the query parameter: we fetch each page once per
# (source, location) and match every profile query against it locally.


def _is_scroll_feed(src: JobSource) -> bool:
    return bool(getattr(src, "scroll_feed", False))


def offer_haystack(offer) -> str:
    """Normalized free-text of an Offer used for local query sieving."""
    parts = [offer.title, offer.company, offer.location,
             offer.category, " ".join(offer.tags or [])]
    return " ".join(str(p) for p in parts if p).replace("-", " ")


def run_sync(
    config: Config,
    conn,
    sources: dict[str, JobSource],
    *,
    run: Run | None = None,
    family_filter: str | None = None,
    max_pages: int | None = None,
    max_results_per_query: int | None = None,
    dry_run: bool = False,
    snapshot_dir: Path | None = None,
    sleep_s: float = 0.5,
) -> SyncStats:
    """Run the full search and persist offers."""
    stats = SyncStats()
    run_id = run.id if run else None
    max_pages = max_pages or config.search.max_pages_per_query
    page_size = max_results_per_query or config.search.max_results_per_query
    snap = snapshot_dir or config.snapshot_dir
    snapshots: dict[str, list[Any]] = {}

    def record(source: str, offers: list, stored: list[int]) -> None:
        bucket = stats.stored.setdefault(source, [0, 0, 0])
        for i, value in enumerate(stored):
            bucket[i] += value
        stats.raw_rows[source] = stats.raw_rows.get(source, 0) + len(offers)
        stats.total_inserted += stored[0]
        stats.total_updated += stored[1]
        stats.total_dupes += stored[2]

    def store_offers(source: str, offers: list, family_id: str, query: str) -> None:
        for offer in offers:
            offer.family = offer.family or guess_family(config, offer, family_id)
            offer.query = query
        if not dry_run and run_id:
            stored = store.upsert_offers(conn, run_id, offers).get(source, [0, 0, 0])
            record(source, offers, stored)
        stats.seen_by_family[family_id] = stats.seen_by_family.get(family_id, 0) + len(offers)

    def fetch_scroll_pages(
        src: JobSource, location: SearchLocation,
    ) -> list[SourcePage]:
        pages: list[SourcePage] = []
        for page in range(1, max_pages + 1):
            try:
                result = src.search("", location, page=page, page_size=page_size)
            except SourceUnavailable as exc:
                stats.disabled.setdefault(src.name, str(exc))
                break
            except SourceError as exc:
                stats.disabled.setdefault(f"{src.name}[page {page}]", str(exc))
                break
            stats.calls[src.name] = stats.calls.get(src.name, 0) + 1
            stats.raw_rows.setdefault(src.name, 0)
            snapshots.setdefault(src.name, []).append(asdict(result))
            pages.append(result)
            if not result.has_more:
                break
            time.sleep(sleep_s)
        return pages

    families = [f for f in config.families if family_filter is None or f.id == family_filter]
    scroll_pools: dict[tuple[str, str], list[SourcePage]] = {}

    for family in families:
        for src_name in family.sources:
            if src_name not in sources:
                continue
            src = sources[src_name]
            for location in resolve_locations(src, config, family):
                if _is_scroll_feed(src):
                    pool_key = (src_name, location.name)
                    if pool_key not in scroll_pools:
                        scroll_pools[pool_key] = fetch_scroll_pages(src, location)
                    slot = PlannedQuery(family=family, source=src_name, location=location, query="")
                    for query in slot.queries:
                        for page in scroll_pools[pool_key]:
                            matched = [
                                offer for offer in page.offers
                                if matches_query(offer_haystack(offer), query)
                            ]
                            if matched:
                                store_offers(src_name, matched, family.id, query)
                    continue
                slot = PlannedQuery(family=family, source=src_name, location=location, query="")
                for query in slot.queries:
                    page = 1
                    while True:
                        try:
                            result = src.search(query, location, page=page, page_size=page_size)
                        except SourceUnavailable as exc:
                            stats.disabled.setdefault(src_name, str(exc))
                            break
                        except SourceError as exc:
                            stats.disabled.setdefault(f"{src_name}[{query}]", str(exc))
                            break
                        stats.calls[src_name] = stats.calls.get(src_name, 0) + 1
                        stats.raw_rows.setdefault(src_name, 0)
                        snapshots.setdefault(src_name, []).append(asdict(result))
                        stats.seen_by_family[family.id] = stats.seen_by_family.get(family.id, 0) + len(result.offers)

                        if not result.offers:
                            if not result.has_more or page >= max_pages:
                                break
                            page += 1
                            time.sleep(sleep_s)
                            continue

                        store_offers(src_name, list(result.offers), family.id, query)

                        if not result.has_more or page >= max_pages:
                            break
                        page += 1
                        time.sleep(sleep_s)
                    time.sleep(sleep_s * 0.5)

    # Targeted ATS pass: watch-list companies are full-board, family-agnostic.
    for src_name in ("greenhouse", "lever"):
        source = sources.get(src_name)
        if source is None:
            continue
        for company in config.ats_companies.get(src_name, []):
            try:
                for batch in _iter_company(source, company, page_size=200, max_pages=max_pages):
                    stats.calls[src_name] = stats.calls.get(src_name, 0) + 1
                    stats.raw_rows.setdefault(src_name, 0)
                    snapshots.setdefault(src_name, []).append(asdict(batch))
                    for offer in batch:
                        offer.family = guess_family(config, offer, "target")
                    stats.seen_by_family["target"] = stats.seen_by_family.get("target", 0) + len(batch)
                    if not dry_run and run_id:
                        stored = store.upsert_offers(conn, run_id, batch).get(src_name, [0, 0, 0])
                        record(src_name, batch, stored)
            except (SourceError, SourceUnavailable) as exc:
                stats.disabled[f"{src_name}[{company}]"] = str(exc)

    if not dry_run:
        stats.total_stored = store.count_offers(conn)

        if snap is not None:
            run_folder = snap / f"run-{run_id}"
            run_folder.mkdir(parents=True, exist_ok=True)
            for source, payloads in snapshots.items():
                lines = [json.dumps(p, ensure_ascii=False) for p in payloads]
                (run_folder / f"{source}.jsonl").write_text("\n".join(lines), encoding="utf-8")
            (run_folder / "manifest.json").write_text(
                json.dumps(stats.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
    return stats


def _iter_company(source: JobSource, company: str, page_size: int = 200, max_pages: int = 5):
    page = 1
    fallback = SearchLocation(name="Target", adzuna_country=None)
    while True:
        result = source.search(company, fallback, page=page, page_size=page_size)
        if result.offers:
            yield result.offers
        if not result.has_more or page >= max_pages:
            break
        page += 1
        time.sleep(0.2)
