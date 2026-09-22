"""Source adapters turn each job board's own payloads into normalized Offers.

The pipeline only ever talks to the :class:`JobSource` interface, so adding a
new board (or later a Rezi/MCP backend if you get a Pro account) is a matter of
writing one adapter.
"""

from __future__ import annotations

import abc
import html
import os
import re
from typing import Any

import httpx

from ..config import SearchLocation
from ..models import Offer, SourcePage

DEFAULT_TIMEOUT = float(os.environ.get("JOBSOURCE_TIMEOUT_SECONDS", "30"))
DEFAULT_USER_AGENT = os.environ.get(
    "JOBSOURCE_USER_AGENT", "jobpilot/0.1 (personal job application agent)"
)

_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"[a-z0-9]+")


def query_tokens(query: str) -> list[str]:
    """Meaningful lowercase tokens from a search query."""
    return [t for t in (query or "").lower().replace("-", " ").split() if len(t) > 2]


def _common_prefix_len(a: str, b: str) -> int:
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return i


def _word_matches(word: str, token: str) -> bool:
    word = word.strip("_-")
    token = token.strip("_-")
    if not word or not token:
        return False
    if word == token:
        return True
    # token as prefix: engineer -> engineering(s)
    if len(token) >= 4 and token in word:
        return True
    # shared root with enough overlap: robot <-> robotics, embedded <-> embedding.
    # (a bare 4-char prefix is NOT enough: autonomous != automation).
    n = min(len(word), len(token))
    if n >= 4:
        prefix = _common_prefix_len(word, token)
        if prefix >= 4 and prefix / n >= 0.6:
            return True
    return False


def matches_query(haystack: str, query: str) -> bool:
    """True when ``query`` (phrase or all root-matching tokens) is in ``haystack``.

    Board search parameters are unreliable (behaviour varies per source), so every
    adapter applies this client-side relevance sieve before turning raw rows into
    :class:`Offer` objects. Token matching is root-prefix based (robot <-> robotics,
    engineer <-> engineering) to survive plurals and gerunds without piling up noise.
    """
    query_l = (query or "").lower().strip()
    haystack_l = (haystack or "").lower().replace("-", " ")
    if not query_l:
        return True
    if query_l in haystack_l:
        return True
    tokens = query_tokens(query_l)
    if not tokens:
        return True
    words = _WORD_RE.findall(haystack_l)
    return all(any(_word_matches(w, t) for w in words) for t in tokens)


class SourceError(Exception):
    """Transient failure talking to a job board."""


class SourceUnavailable(SourceError):
    """The source can't be used right now (e.g. missing API key)."""


def html_to_text(raw: Any, max_len: int | None = None) -> str:
    """Strip HTML tags and entities from a description but keep paragraphs."""
    if raw is None:
        return ""
    text = html.unescape(str(raw))
    text = re.sub(r"<(br|/p|/div|/li|/h[1-6])[^>]*>", "\n", text)
    text = _TAG_RE.sub(" ", text)
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    if max_len:
        text = text[:max_len]
    return text.strip()


_CURRENCY_SYMBOL = [
    ("USD", r"\$|usd|us ?\$"),
    ("EUR", r"€|eur|euros?"),
    ("GBP", r"£|gbp"),
    ("CAD", r"cad"),
    ("AUD", r"aud"),
]


def _strip_currency(value: str) -> str:
    return re.sub(r"[$,£€\u00a0]", "", value).strip().lower()


def extract_salary_range(text: str | None) -> tuple[float | None, float | None, str]:
    """Best-effort parse of a salary text like ``$120k - $160k`` or ``45000-55000``.

    Returns ``(salary_min, salary_max, currency)`` with unknown parts as None.
    """
    if not text:
        return None, None, ""
    value = _strip_currency(text)
    matches = re.findall(r"(\d(?:[\d.,]*\d)?)\s*(k)?", value, flags=re.IGNORECASE)
    currency = ""
    for sym, pattern in _CURRENCY_SYMBOL:
        if re.search(pattern, text, flags=re.IGNORECASE):
            currency = sym
            break

    def _norm(digits: str, suffix: str | None) -> float:
        suffix = suffix or ""
        if suffix.lower() == "k":
            return float(digits.replace(",", "").replace(".", "")) * 1000.0
        return float(digits.replace(",", "").replace(".", ""))

    scaled: list[float] = []
    for digits, suffix in matches:
        if not digits:
            continue
        try:
            scaled.append(_norm(digits, suffix))
        except ValueError:
            continue
    if not scaled:
        return None, None, currency
    if len(scaled) == 1:
        return scaled[0], None, currency
    lo, hi = scaled[0], scaled[1]
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi, currency


class JobSource(abc.ABC):
    """Interface every board adapter implements."""

    name: str = "base"
    remote_first: bool = False
    scroll_feed: bool = False  # query param is ignored: fetch once, sieve locally
    requires_key: bool = False

    def __init__(self, timeout: float = DEFAULT_TIMEOUT,
                 user_agent: str = DEFAULT_USER_AGENT) -> None:
        self.timeout = timeout
        self.user_agent = user_agent

    # -- HTTP helper ------------------------------------------------ #
    def _get_json(self, url: str, params: dict | None = None,
                  headers: dict | None = None) -> Any:
        request_headers = {"User-Agent": self.user_agent}
        if headers:
            request_headers.update(headers)
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(url, params=params, headers=request_headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as exc:
            raise SourceError(f"{self.name}: request failed for {url}: {exc}") from exc
        except ValueError as exc:  # invalid JSON
            raise SourceError(f"{self.name}: bad JSON from {url}: {exc}") from exc

    # -- interface -------------------------------------------------- #
    @abc.abstractmethod
    def search(
        self,
        query: str,
        location: SearchLocation,
        page: int = 1,
        page_size: int = 50,
    ) -> SourcePage:
        """Fetch one page of results for a query/location pair."""

    @staticmethod
    def locations() -> list[SearchLocation]:
        """Which locations this source can meaningfully sieve with."""
        return [SearchLocation(name="Remote", adzuna_country=None)]

    def parse_offers(self, raw: Any) -> list[Offer]:
        """Adapter-specific mapping from raw payloads to Offers."""
        raise NotImplementedError
