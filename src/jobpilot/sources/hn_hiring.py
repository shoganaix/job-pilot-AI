"""Hacker News "Ask HN: Who is hiring?" adapter (keyless, via the Algolia HN API).

Every month ``whoishiring`` posts a thread where employers comment one opening
per comment, in a loose ``Company | Role | Location | Salary`` convention. It is
the one board that surfaces small companies and space/robotics shops which never
make it to Adzuna or the big ATS boards.

The adapter is a *scroll feed*: it walks the thread's comments with Algolia
pagination and the pipeline sieves each family query locally, so the whole thread
is downloaded once per run instead of once per query. Replies to a job post
(``parent_id != story_id``) are dropped: they are discussion, not openings.
"""

from __future__ import annotations

import re
from typing import Any

from ..config import SearchLocation
from ..models import Offer, SourcePage
from .base import (
    DEFAULT_USER_AGENT,
    JobSource,
    SourceError,
    extract_salary_range,
    html_to_text,
)

ALGOLIA = "https://hn.algolia.com/api/v1"
HN_ITEM = "https://news.ycombinator.com/item?id={id}"

#: The HN index caps hitsPerPage at 100.
_MAX_PAGE_SIZE = 100

#: Only the monthly hiring thread. The author's other thread that month,
#: "Who wants to be hired?", is candidates advertising themselves: no offers.
_HIRING_TITLE_RE = re.compile(r"^Ask HN: Who is hiring\? \(.+\)$", re.IGNORECASE)

_REMOTE_RE = re.compile(r"\bremote\b", re.IGNORECASE)
_HREF_RE = re.compile(r"href=\"(https?://[^\"]+)\"", re.IGNORECASE)
_HN_HOSTS = ("news.ycombinator.com", "ycombinator.com", "hn.algolia.com")

#: A header segment only counts as a salary when it carries a currency marker.
#: The convention is one field per pipe, so the money is isolated there instead of
#: letting the whole header be scanned: that is what turned "2+ years" into a
#: salary of 2 and "Superset (YC P26)" into a low end of 26.
_SALARY_HINT_RE = re.compile(
    r"[$€£]|\b(usd|eur|gbp|cad|aud)\b|salary|salario|compensation|pay range",
    re.IGNORECASE,
)
#: Hourly rates are not comparable with the annual ranges the scoring uses.
_HOURLY_RE = re.compile(r"/\s*(hr|hour)\b|per hour|hourly", re.IGNORECASE)
#: Anything below this is a misparse, not a posting (the smallest sane annual pay).
_MIN_ANNUAL = 10_000.0

_URL_RE = re.compile(r"^(https?://|www\.)\S+", re.IGNORECASE)
#: Fields that read as a location rather than a role, used when a link sits in
#: the role slot: "Acme | https://jobs.acme.io/1 | (REMOTE EU)".
_LOCATIONISH_RE = re.compile(r"^\s*[([]|\bremote\b|\bonsite\b|\bhybrid\b|\banywhere\b", re.IGNORECASE)


def _salary(segments: list[str]) -> tuple[float | None, float | None, str]:
    """Parse the one pipe segment that is actually about pay."""
    for segment in segments:
        if not _SALARY_HINT_RE.search(segment) or _HOURLY_RE.search(segment):
            continue
        low, high, currency = extract_salary_range(segment)
        if low is not None and low < _MIN_ANNUAL:
            continue
        if high is not None and high < _MIN_ANNUAL:
            continue
        return low, high, currency
    return None, None, ""


def _fallback_title(body: str) -> str:
    """First sentence of the post body, for posts whose role field is just a URL."""
    first = next((line.strip() for line in body.splitlines() if line.strip()), "")
    first = re.split(r"(?<=[.!?])\s", first)[0]
    return first[:120] if len(first) > 20 else ""


def _is_hn_link(url: str) -> bool:
    return any(host in url for host in _HN_HOSTS)


def _first_link(html: str) -> str:
    """First external link in the comment body (the employer's apply page)."""
    for url in _HREF_RE.findall(html or ""):
        if not _is_hn_link(url):
            return url
    return ""


def _split_header(comment_text: str) -> tuple[str, str, str, list[str], str]:
    """Split the pipe header into (company, title, location, segments, role_url).

    The convention is ``Company | Role | Location | ...`` before the first
    paragraph, but employers deviate. Anything without pipes is rejected by the
    caller: we cannot tell a company name from prose.

    Some posts put a link where the role belongs ("Acme | https://jobs.acme.io/1
    | Senior iOS Engineer | Paris"). The link is dropped and the field after it is
    promoted to the title, otherwise the role lands in the location and the
    seniority filter never sees it. That link is returned separately as the apply
    URL: it is more specific than any other link in the post.
    """
    head = re.split(r"<p>|\n", comment_text or "", maxsplit=1)[0]
    head = html_to_text(head)
    parts = [p.strip() for p in head.split("|") if p.strip()]
    if len(parts) < 2:
        return "", "", "", [], ""
    company = parts[0]
    if _URL_RE.match(parts[1]):
        url, _, trailing = parts[1].partition(" ")
        after = parts[2:]
        if after and not _LOCATIONISH_RE.search(after[0]):
            title = after[0]
            location = after[1] if len(after) > 1 else (trailing or head)
        else:
            title = url  # caller swaps in the first sentence of the body
            location = after[0] if after else (trailing or head)
        return company, title, location, parts, url
    title = parts[1]
    location = parts[2] if len(parts) > 2 else head
    return company, title, location, parts, ""


class HNWhoIsHiringSource(JobSource):
    name = "hn_hiring"
    remote_first = True
    scroll_feed = True

    def __init__(self, timeout: float = 30.0, user_agent: str = "") -> None:
        super().__init__(timeout=timeout, user_agent=user_agent or DEFAULT_USER_AGENT)
        self._story_id: str = ""
        self._pages: dict[int, dict] = {}
        self._nb_pages: int = 0

    # -- thread discovery ------------------------------------------- #
    def _find_story(self) -> str:
        """Object ID of the most recent "Who is hiring?" thread."""
        if self._story_id:
            return self._story_id
        payload = self._get_json(
            f"{ALGOLIA}/search_by_date",
            params={"tags": "story,author_whoishiring", "hitsPerPage": 5},
        )
        hits = payload.get("hits", []) if isinstance(payload, dict) else []
        for hit in hits:
            if _HIRING_TITLE_RE.match(str(hit.get("title", ""))):
                self._story_id = str(hit.get("objectID", ""))
                return self._story_id
        raise SourceError(f"{self.name}: no 'Who is hiring?' thread found")

    def _fetch_comments(self, api_page: int, page_size: int) -> dict:
        story_id = self._find_story()
        payload = self._get_json(
            f"{ALGOLIA}/search_by_date",
            params={
                "tags": f"comment,story_{story_id}",
                "hitsPerPage": min(max(page_size, 1), _MAX_PAGE_SIZE),
                "page": max(api_page, 0),
            },
        )
        return payload if isinstance(payload, dict) else {}

    def _comments_page(self, page: int, page_size: int) -> dict:
        """One page of comments, newest first.

        Algolia returns the thread oldest-first, so a pipeline that stops after
        ``max_pages`` would only ever see the postings from the first days of the
        month. Walking the pages backwards hands it the freshest ones instead;
        the first call spends one extra request reading ``nbPages``.
        """
        if page in self._pages:
            return self._pages[page]
        if not self._nb_pages:
            probe = self._fetch_comments(0, page_size)
            self._nb_pages = max(int(probe.get("nbPages", 1) or 1), 1)
        api_page = max(self._nb_pages - page, 0)  # Algolia pages are 0-based
        payload = self._fetch_comments(api_page, page_size)
        self._pages[page] = payload
        return payload

    def search(
        self,
        query: str,
        location: SearchLocation,
        page: int = 1,
        page_size: int = 50,
    ) -> SourcePage:
        payload = self._comments_page(page, page_size)
        hits = payload.get("hits", []) or []
        story_id = self._find_story()
        posts = [h for h in hits if str(h.get("parent_id", "")) == story_id]
        return SourcePage(
            offers=self.parse_offers(posts),
            has_more=page < self._nb_pages,
            total_found=len(posts),
        )

    # -- mapping ------------------------------------------------------ #
    def parse_offers(self, raw: Any) -> list[Offer]:
        return [offer for offer in (self._parse(h) for h in raw or []) if offer is not None]

    def _parse(self, hit: dict) -> Offer | None:
        comment_text = str(hit.get("comment_text", "") or "")
        company, title, loc, segments, role_url = _split_header(comment_text)
        if not company or not title:
            return None  # not a job post (meta comment, follow-up question, ...)
        description = html_to_text(comment_text)
        if _URL_RE.match(title):
            # "Company | https://jobs.example.com/123 | REMOTE": the role field is
            # a link and nothing follows it, so borrow the body's first sentence.
            body = re.split(r"<p>|\n", comment_text, maxsplit=1)
            title = _fallback_title(html_to_text(body[1] if len(body) > 1 else "")) or f"Role at {company}"
        source_id = str(hit.get("objectID", "") or "")
        item_url = HN_ITEM.format(id=source_id)
        header = re.split(r"<p>|\n", comment_text, maxsplit=1)[0]
        salary_min, salary_max, currency = _salary(segments)
        apply_url = role_url or _first_link(comment_text) or item_url
        return Offer(
            source=self.name,
            source_id=source_id,
            title=title,
            company=company,
            location=loc,
            remote=bool(_REMOTE_RE.search(header)),
            url=item_url,
            apply_url=apply_url,
            description=description,
            salary_min=salary_min,
            salary_max=salary_max,
            currency=currency,
            published_at=str(hit.get("created_at", "")) or None,
            query="",
            raw=hit,
        )
