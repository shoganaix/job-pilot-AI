"""Tests for the source adapters against frozen fixtures."""

from jobpilot.config import SearchLocation
from jobpilot.sources.adzuna import AdzunaSource
from jobpilot.sources.arbeitnow import ArbeitnowSource
from jobpilot.sources.ats_boards import GreenhouseSource, LeverSource
from jobpilot.sources.himalayas import HimalayasSource
from jobpilot.sources.remoteok import RemoteOKSource

from ._util import fixture

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
