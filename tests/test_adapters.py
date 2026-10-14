"""Tests for the source adapters against frozen fixtures."""

from jobpilot.config import SearchLocation
from jobpilot.sources.adzuna import AdzunaSource
from jobpilot.sources.arbeitnow import ArbeitnowSource
from jobpilot.sources.ats_boards import GreenhouseSource, LeverSource
from jobpilot.sources.devglobaljobs import DevGlobalJobsSource
from jobpilot.sources.himalayas import HimalayasSource
from jobpilot.sources.hn_hiring import HNWhoIsHiringSource
from jobpilot.sources.remoteok import RemoteOKSource

from ._util import fixture, sample_config

SPAIN = SearchLocation(name="Spain", adzuna_country="es")
REMOTE = SearchLocation(name="Remote", adzuna_country=None)


def test_adzuna_search():
    src = AdzunaSource(app_id="x", app_key="y")
    src._get_json = lambda url, params=None, headers=None: fixture("adzuna_page.json")
    page = src.search("Robotics Engineer", SPAIN, page=1, page_size=50)
    assert page.total_found == 98
    offer = page.offers[0]
    assert offer.source == "adzuna"
    assert offer.title == "Robotics Software Engineer"
    assert offer.salary_min == 32000 and offer.salary_max == 44000
    assert "Madrid" in offer.location
    assert offer.apply_url


def test_adzuna_drops_non_tech_categories():
    src = AdzunaSource(app_id="x", app_key="y")
    raw = [
        {"id": "t1", "title": "Nursery Practitioner",
         "category": {"label": "Teaching Jobs"}, "company": {"display_name": "X"}, "location": {"area": []}},
        {"id": "t2", "title": "Camare r a", "category": {"label": "Stellen aus Gastronomie & Catering"},
         "company": {"display_name": "X"}, "location": {"area": []}},
        {"id": "t3", "title": "Eng de robótica", "category": {"label": "Engineering Jobs"},
         "company": {"display_name": "ACME"}, "location": {"area": ["Spain", "Madrid"]}},
    ]
    offers = src.parse_offers(raw)
    assert [o.title for o in offers] == ["Eng de robótica"]


def test_arbeitnow_search():
    src = ArbeitnowSource()
    src._get_json = lambda url, params=None, headers=None: fixture("arbeitnow_page.json")
    page = src.search("embedded", REMOTE, page=1)
    assert page.has_more is True
    offer = page.offers[0]
    assert offer.company == "RoboWorks GmbH"
    assert offer.salary_min == 60000 and offer.salary_max == 75000
    assert offer.remote is True
    assert "RTOS" in offer.description.upper()


def test_remoteok_search_filters_and_paginates():
    src = RemoteOKSource()
    feed = fixture("remoteok_feed.json")
    src._feed = [item for item in feed if isinstance(item, dict) and item.get("id")]
    page = src.search("Computer Vision Engineer", REMOTE, page=1, page_size=1)
    assert len(page.offers) == 1
    assert page.has_more is False  # only 1 match, page 1 of size 1 is the last
    assert page.offers[0].title == "Computer Vision Engineer"
    assert page.offers[0].salary_max == 130000
    # a second page of the same 1-match set is empty
    page2 = src.search("Computer Vision Engineer", REMOTE, page=2, page_size=1)
    assert page2.offers == []


def test_himalayas_search():
    src = HimalayasSource()
    src._get_json = lambda url, params=None, headers=None: fixture("himalayas_page.json")
    page = src.search("Robotics Engineer", REMOTE, page=1)
    assert len(page.offers) == 1
    offer = page.offers[0]
    assert offer.title == "Robotics Engineer (ROS2)"
    assert offer.salary_min == 70000 and offer.currency == "EUR"
    assert offer.seniority and "senior" in offer.seniority


def test_greenhouse_search():
    src = GreenhouseSource(companies=["redrover"])
    src._get_json = lambda url, params=None, headers=None: fixture("greenhouse_jobs.json")
    page = src.search("redrover", SPAIN, page=1)
    offer = page.offers[0]
    assert offer.title == "Vehicle Test Engineer"
    assert offer.company == "Red Rover Motors"
    assert "validation" in offer.description.lower()


def test_lever_search():
    src = LeverSource(companies=["spaceco"])
    src._get_json = lambda url, params=None, headers=None: fixture("lever_postings.json")
    page = src.search("spaceco", SPAIN, page=1)
    offer = page.offers[0]
    assert offer.source == "lever"
    assert offer.title == "Avionics Test Engineer"
    assert offer.salary_min == 100000
    assert "El Segundo" in offer.location
    assert "Remote" in offer.location


# --- Hacker News "Who is hiring?" ------------------------------------- #

HN_STORIES = {
    "hits": [
        {
            "title": "Ask HN: Who is hiring? (October 2026)",
            "objectID": "49922569",
            "author": "whoishiring",
        }
    ]
}


def _hn_source() -> HNWhoIsHiringSource:
    src = HNWhoIsHiringSource()

    def fake(url, params=None, headers=None):
        if "tags" in (params or {}) and str(params["tags"]).startswith("story,"):
            return HN_STORIES
        return fixture("hn_hiring_comments.json")

    src._get_json = fake
    return src


def test_hn_hiring_parses_pipe_headers():
    page = _hn_source().search("Robotics Engineer", REMOTE, page=1, page_size=100)
    titles = [o.title for o in page.offers]
    assert titles == ["Software Engineer, Flight Software (C++, Linux)", "Senior Backend Engineer, Medical Data Pipeline (Python + Rust)"]
    offer = page.offers[0]
    assert offer.source == "hn_hiring"
    assert offer.source_id == "50095921"
    assert offer.company == "Varda Space"
    assert offer.remote is True
    assert "REMOTE (EU)" in offer.location
    assert offer.apply_url == "https://boards.greenhouse.io/varda/jobs/910001"
    assert offer.url == "https://news.ycombinator.com/item?id=50095921"
    assert "GNC" in offer.description


def test_hn_hiring_parses_salary():
    senior = _hn_source().search("backend", REMOTE, page=1, page_size=100).offers[1]
    assert senior.salary_min == 170000
    assert senior.salary_max == 210000
    assert senior.currency == "USD"


def test_hn_hiring_drops_replies_and_prose():
    # 4 comments in the fixture: 2 job posts, 1 reply to a post (different parent),
    # 1 prose comment (top-level but no "Company | Role" header)
    page = _hn_source().search("", REMOTE, page=1, page_size=100)
    assert page.total_found == 3  # top-level comments only, replies already dropped
    assert len(page.offers) == 2  # the prose comment is not a job post
    assert page.has_more is False


def test_hn_hiring_falls_back_to_item_url():
    raw = [
        {
            "objectID": "123",
            "parent_id": "49922569",
            "comment_text": "Tiny Startup | Junior Embedded Engineer (C) | Madrid, Spain<p>Apply by email.",
        }
    ]
    offer = _hn_source().parse_offers(raw)[0]
    assert offer.apply_url == "https://news.ycombinator.com/item?id=123"
    assert offer.remote is False


def test_hn_hiring_ignores_years_as_salary():
    # "2+ years" in the header must not become a 2.0 salary
    raw = [
        {
            "objectID": "77",
            "parent_id": "49922569",
            "comment_text": "Acme | DevOps Engineer | ONSITE (Madrid) | 2+ years<p>Not salary text.",
        }
    ]
    offer = _hn_source().parse_offers(raw)[0]
    assert offer.salary_min is None and offer.salary_max is None
    assert offer.remote is False


def test_hn_hiring_salary_only_from_the_pay_segment():
    raw = [
        {
            "objectID": "78",
            "parent_id": "49922569",
            "comment_text": (
                "Typify.dev ( https://typify.dev ) | AI Application Engineer | "
                "San Francisco (hybrid) | Full-time, 2+ years | $180k - $220k"
            ),
        },
        {
            "objectID": "79",
            "parent_id": "49922569",
            "comment_text": "StartupHakk | AI Engineer Apprentice | Remote (US) | $7.25-$10/hr",
        },
    ]
    offers = _hn_source().parse_offers(raw)
    assert offers[0].salary_min == 180000 and offers[0].salary_max == 220000
    # hourly pay is not an annual range: better no salary than a wrong one
    assert offers[1].salary_min is None


def test_hn_hiring_title_falls_back_when_role_field_is_a_url():
    raw = [
        {
            "objectID": "80",
            "parent_id": "49922569",
            "comment_text": (
                "3Gimbals | https://www.linkedin.com/jobs/view/4477632187 (US/Remote)<p>"
                "Hiring entry level full stack engineers with strong Python and SQL."
            ),
        }
    ]
    offer = _hn_source().parse_offers(raw)[0]
    assert not offer.title.startswith("http")
    assert "full stack" in offer.title.lower()
    assert offer.company == "3Gimbals"
    assert "Remote" in offer.location


def test_hn_hiring_promotes_role_after_a_link():
    # the real Purchasely post: a link sits in the role slot and the seniority
    # must not end up hidden in the location
    raw = [
        {
            "objectID": "81",
            "parent_id": "49922569",
            "comment_text": (
                "Purchasely ( https://purchasely.com ) | https://www.purchasely.com/jobs |"
                " Senior iOS SDK Engineer | Paris, France | REMOTE (France) | Full-time (CDI)<p>"
                "We are an in-app monetization platform."
            ),
        }
    ]
    offer = _hn_source().parse_offers(raw)[0]
    assert offer.title == "Senior iOS SDK Engineer"
    assert "Paris" in offer.location
    assert offer.remote is True
    assert offer.apply_url == "https://www.purchasely.com/jobs"


# --- Dev Global Jobs ---------------------------------------------------- #


def test_devglobaljobs_maps_feed():
    src = DevGlobalJobsSource()
    src._get_json = lambda url, params=None, headers=None: fixture("devglobaljobs_feed.json")
    page = src.search("", REMOTE, page=1, page_size=50)
    assert len(page.offers) == 3
    offer = page.offers[0]
    assert offer.source == "devglobaljobs"
    assert offer.source_id == "163319006"
    assert offer.company == "Cloudflare"
    assert offer.remote is True  # "Distributed"
    assert offer.apply_url == "https://boards.greenhouse.io/cloudflare/jobs/8279967?gh_jid=8279967"
    assert offer.url == "https://devglobaljobs.com/jobs/detail/163319006"
    assert offer.category == "sales"
    junior = page.offers[2]
    assert junior.remote is False
    assert junior.country == "Germany"
    assert "ROS2" in junior.description


def test_devglobaljobs_paginates_and_skips_broken_items():
    src = DevGlobalJobsSource()
    src._get_json = lambda url, params=None, headers=None: fixture("devglobaljobs_feed.json")
    first = src.search("", REMOTE, page=1, page_size=2)
    assert len(first.offers) == 2
    assert first.has_more is True
    second = src.search("", REMOTE, page=2, page_size=2)
    assert len(second.offers) == 1
    assert second.has_more is False
    assert src.parse_offers([{"id": "1", "title": "", "organization": "X"}]) == []


def test_hn_hiring_walks_pages_backwards_from_the_newest():
    requested = []

    def fake(url, params=None, headers=None):
        tags = str((params or {}).get("tags", ""))
        if tags.startswith("story,"):
            return HN_STORIES
        requested.append((params or {}).get("page"))
        return {
            "hits": [
                {
                    "objectID": str(1000 + (params or {}).get("page", 0)),
                    "parent_id": "49922569",
                    "comment_text": "Co | Role | REMOTE",
                }
            ],
            "nbPages": 4,
        }

    src = HNWhoIsHiringSource()
    src._get_json = fake
    first = src.search("", REMOTE, page=1, page_size=100)
    assert first.has_more is True
    src.search("", REMOTE, page=2, page_size=100)
    # probe (page 0) then the two newest pages, walking backwards
    assert requested == [0, 3, 2]


def test_new_sources_build_without_keys(tmp_path):
    from jobpilot.sources.registry import SOURCE_META, build_source

    config = sample_config(tmp_path)
    assert build_source("hn_hiring", config).name == "hn_hiring"
    assert build_source("devglobaljobs", config).name == "devglobaljobs"
    assert SOURCE_META["hn_hiring"] and SOURCE_META["devglobaljobs"]
