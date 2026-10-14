"""Build source adapters from the profile config."""

from __future__ import annotations

from ..config import Config
from .adzuna import AdzunaSource
from .arbeitnow import ArbeitnowSource
from .ats_boards import GreenhouseSource, LeverSource
from .base import JobSource, SourceUnavailable
from .devglobaljobs import DevGlobalJobsSource
from .himalayas import HimalayasSource
from .hn_hiring import HNWhoIsHiringSource
from .remoteok import RemoteOKSource

# Human-friendly descriptions of each source, used by the CLI explainer.
SOURCE_META: dict[str, str] = {
    "adzuna": "EU/ES aggregator (free key). Short excerpts only.",
    "arbeitnow": "Keyless European remote-first feed, full descriptions.",
    "remoteok": "Keyless global remote tech board.",
    "himalayas": "Keyless remote jobs, structured salary/seniority.",
    "hn_hiring": "Keyless HN 'Who is hiring?' monthly thread (startups).",
    "devglobaljobs": "Keyless Dev Global Jobs feed (30 newest ATS postings).",
    "greenhouse": "Target-company ATS boards (keyless).",
    "lever": "Target-company ATS postings (keyless).",
}


def build_source(name: str, config: Config) -> JobSource:
    if name == "adzuna":
        return AdzunaSource()
    if name == "arbeitnow":
        return ArbeitnowSource()
    if name == "remoteok":
        return RemoteOKSource()
    if name == "himalayas":
        return HimalayasSource()
    if name == "hn_hiring":
        return HNWhoIsHiringSource()
    if name == "devglobaljobs":
        return DevGlobalJobsSource()
    if name == "greenhouse":
        return GreenhouseSource(companies=config.ats_companies.get("greenhouse", []))
    if name == "lever":
        return LeverSource(companies=config.ats_companies.get("lever", []))
    raise SourceUnavailable(f"unknown source: {name}")


def build_sources(config: Config, requested: list[str] | None = None) -> tuple[dict[str, JobSource], dict[str, str]]:
    """Instantiate all enabled sources.

    Returns ``(sources, disabled)`` where *disabled* maps a source name to the
    reason it can't be started (e.g. missing Adzuna key).
    """
    wanted = requested or config.sources
    sources: dict[str, JobSource] = {}
    disabled: dict[str, str] = {}
    for name in wanted:
        try:
            sources[name] = build_source(name, config)
        except SourceUnavailable as exc:
            disabled[name] = str(exc)
    return sources, disabled
