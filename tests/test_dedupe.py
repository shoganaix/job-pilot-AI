"""Tests for cross-source de-duplication."""

from jobpilot.dedupe import batch_dedupe, compute_dedupe_hash
from jobpilot.models import Offer


def _offer(source, sid, title="Robotics Engineer", company="ACME", location="Madrid"):
    return Offer(source=source, source_id=sid, title=title, company=company, location=location)


def test_hash_stable_across_sources():
    h1 = compute_dedupe_hash(_offer("adzuna", "a1"))
    h2 = compute_dedupe_hash(_offer("remoteok", "r1"))
    assert h1 == h2


def test_hash_differs_on_company():
    assert compute_dedupe_hash(_offer("a", "1")) != compute_dedupe_hash(
        _offer("a", "1", company="Other")
    )


def test_batch_dedupe_keeps_first():
    o1 = _offer("adzuna", "a1")
    o2 = _offer("remoteok", "r1")
    o3 = _offer("remoteok", "r2", title="Frontend")
    unique, dupes = batch_dedupe([o1, o2, o3])
    assert len(unique) == 2
    assert len(dupes) == 1
    assert dupes[0].source_id == "r1"
