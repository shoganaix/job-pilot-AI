"""SQLite persistence layer.

Single database file (default ``data/jobpilot.db``) holding runs, normalized
offers, per-run scores, the application queue and generated CV variants.
Everything is git-ignored; personal data never leaves the repo.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .dedupe import compute_dedupe_hash
from .models import AppStatus, Offer, Run, Score

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    notes       TEXT NOT NULL DEFAULT '',
    stats       TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS offers (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source           TEXT NOT NULL,
    source_id        TEXT NOT NULL,
    dedupe_hash      TEXT NOT NULL,
    title            TEXT NOT NULL,
    company          TEXT NOT NULL,
    location         TEXT NOT NULL DEFAULT '',
    country          TEXT,
    remote           INTEGER,
    url              TEXT NOT NULL DEFAULT '',
    apply_url        TEXT NOT NULL DEFAULT '',
    description      TEXT NOT NULL DEFAULT '',
    salary_min       REAL,
    salary_max       REAL,
    salary_text      TEXT NOT NULL DEFAULT '',
    currency         TEXT NOT NULL DEFAULT '',
    category         TEXT NOT NULL DEFAULT '',
    seniority        TEXT,
    published_at     TEXT,
    first_seen_run   INTEGER,
    last_seen_run    INTEGER,
    UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_offers_dedupe ON offers(dedupe_hash);

CREATE TABLE IF NOT EXISTS offer_families (
    offer_id INTEGER NOT NULL REFERENCES offers(id),
    family   TEXT NOT NULL,
    PRIMARY KEY (offer_id, family)
);

CREATE TABLE IF NOT EXISTS offer_scores (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id     INTEGER NOT NULL REFERENCES offers(id),
    run_id       INTEGER NOT NULL REFERENCES runs(id),
    score        REAL NOT NULL,
    triage       TEXT NOT NULL,
    breakdown    TEXT NOT NULL DEFAULT '{}',
    extracted    TEXT NOT NULL DEFAULT '{}',
    hard_filters TEXT NOT NULL DEFAULT '[]',
    reason       TEXT NOT NULL DEFAULT '',
    UNIQUE(offer_id, run_id)
);

CREATE TABLE IF NOT EXISTS applications (
    offer_id  INTEGER PRIMARY KEY REFERENCES offers(id),
    status    TEXT NOT NULL DEFAULT 'new',
    cv_variant TEXT NOT NULL DEFAULT '',
    cv_file    TEXT NOT NULL DEFAULT '',
    notes      TEXT NOT NULL DEFAULT '',
    url        TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cv_variants (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    family     TEXT NOT NULL,
    job_title  TEXT NOT NULL DEFAULT '',
    content    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #
def run_start(conn: sqlite3.Connection, notes: str = "") -> Run:
    cur = conn.execute(
        "INSERT INTO runs (started_at, notes) VALUES (?, ?)", (_now(), notes)
    )
    conn.commit()
    return Run(id=cur.lastrowid, started_at=_now(), notes=notes)


def run_finish(conn: sqlite3.Connection, run: Run, stats: dict) -> Run:
    conn.execute(
        "UPDATE runs SET stats = ? WHERE id = ?",
        (json.dumps(stats, ensure_ascii=False), run.id),
    )
    conn.commit()
    run.stats = stats
    return run


def latest_run(conn: sqlite3.Connection) -> Run | None:
    row = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return None
    return Run(id=row["id"], started_at=row["started_at"], notes=row["notes"],
               stats=json.loads(row["stats"] or "{}"))


# --------------------------------------------------------------------------- #
# Offers
# --------------------------------------------------------------------------- #
def upsert_offers(conn: sqlite3.Connection, run_id: int, offers: list[Offer]) -> dict:
    """Insert or update a batch of offers.

    Returns ``{source: (inserted, updated, dupes)}`` where *dupes* counts
    offers whose cross-source fingerprint already exists in the database or in
    an earlier row of the same batch (they are collapsed to the first).
    """
    stats: dict[str, list[int]] = {}
    for offer in offers:
        bucket = stats.setdefault(offer.source, [0, 0, 0])
        existing = conn.execute(
            "SELECT id FROM offers WHERE source = ? AND source_id = ?",
            (offer.source, offer.source_id),
        ).fetchone()
        dedupe_hash = compute_dedupe_hash(offer)
        if existing is not None:
            conn.execute(
                """UPDATE offers SET title=?, company=?, location=?, country=?,
                   remote=?, url=?, apply_url=?, description=?, salary_min=?,
                   salary_max=?, salary_text=?, currency=?, category=?,
                   seniority=?, published_at=?, last_seen_run=?
                   WHERE id=?""",
                (
                    offer.title, offer.company, offer.location, offer.country,
                    int(offer.remote) if offer.remote is not None else None,
                    offer.url, offer.apply_url, offer.description,
                    offer.salary_min, offer.salary_max, offer.salary_text,
                    offer.currency, offer.category, offer.seniority,
                    offer.published_at, run_id, existing["id"],
                ),
            )
            offer_id = existing["id"]
            bucket[1] += 1
        else:
            holder = conn.execute(
                "SELECT id FROM offers WHERE dedupe_hash = ? LIMIT 1", (dedupe_hash,)
            ).fetchone()
            if holder is not None:
                bucket[2] += 1
                continue
            cur = conn.execute(
                """INSERT INTO offers (source, source_id, dedupe_hash, title,
                   company, location, country, remote, url, apply_url,
                   description, salary_min, salary_max, salary_text, currency,
                   category, seniority, published_at, first_seen_run,
                   last_seen_run)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    offer.source, offer.source_id, dedupe_hash, offer.title,
                    offer.company, offer.location, offer.country,
                    int(offer.remote) if offer.remote is not None else None,
                    offer.url, offer.apply_url, offer.description,
                    offer.salary_min, offer.salary_max, offer.salary_text,
                    offer.currency, offer.category, offer.seniority,
                    offer.published_at, run_id, run_id,
                ),
            )
            offer_id = cur.lastrowid
            bucket[0] += 1

        if offer.family:
            conn.execute(
                "INSERT OR IGNORE INTO offer_families (offer_id, family) VALUES (?, ?)",
                (offer_id, offer.family),
            )
        else:
            conn.execute(
                "INSERT OR IGNORE INTO offer_families (offer_id, family) VALUES (?, ?)",
                (offer_id, "general"),
            )
    conn.commit()
    return stats  # {source: [inserted, updated, dupes]}


def get_offer(conn: sqlite3.Connection, offer_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM offers WHERE id = ?", (offer_id,)
    ).fetchone()


def list_offers(
    conn: sqlite3.Connection,
    *,
    families: list[str] | None = None,
    sources: list[str] | None = None,
    has_description: bool = False,
    limit: int | None = None,
    offset: int = 0,
) -> list[sqlite3.Row]:
    sql = ("SELECT o.*, (SELECT GROUP_CONCAT(f.family) FROM offer_families f "
           "WHERE f.offer_id = o.id) AS family FROM offers o")
    where: list[str] = []
    params: list = []
    if families:
        sql += " JOIN offer_families f ON f.offer_id = o.id"
        placeholders = ",".join("?" * len(families))
        where.append(f"f.family IN ({placeholders})")
        params.extend(families)
    if sources:
        placeholders = ",".join("?" * len(sources))
        where.append(f"o.source IN ({placeholders})")
        params.extend(sources)
    if has_description:
        where.append("length(o.description) > 0")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY o.id"
    if limit:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    return conn.execute(sql, params).fetchall()


def count_offers(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM offers").fetchone()["n"]


# --------------------------------------------------------------------------- #
# Application queue
# --------------------------------------------------------------------------- #
def set_application(
    conn: sqlite3.Connection,
    offer_id: int,
    status: AppStatus,
    *,
    notes: str = "",
    cv_variant: str = "",
    cv_file: str = "",
) -> None:
    offer = get_offer(conn, offer_id)
    if offer is None:
        raise KeyError(f"offer {offer_id} not found")
    conn.execute(
        """INSERT INTO applications (offer_id, status, cv_variant, cv_file, notes, url, updated_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(offer_id) DO UPDATE SET
             status=excluded.status, cv_variant=excluded.cv_variant,
             cv_file=excluded.cv_file, notes=excluded.notes, url=excluded.url,
             updated_at=excluded.updated_at""",
        (offer_id, status.value, cv_variant, cv_file, notes, offer["apply_url"] or offer["url"], _now()),
    )
    conn.commit()


def get_application(conn: sqlite3.Connection, offer_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM applications WHERE offer_id = ?", (offer_id,)
    ).fetchone()


def list_applications(
    conn: sqlite3.Connection, statuses: list[AppStatus] | None = None
) -> list[sqlite3.Row]:
    sql = """
        SELECT a.offer_id, a.status, a.cv_variant, a.cv_file, a.notes,
               a.url, a.updated_at, o.title, o.company, o.location,
               o.apply_url, o.url AS offer_url, o.description
        FROM applications a JOIN offers o ON o.id = a.offer_id
    """
    if statuses:
        placeholders = ",".join("?" * len(statuses))
        sql += f" WHERE a.status IN ({placeholders})"
        sql += " ORDER BY CASE a.status "
        sql += " WHEN 'apply' THEN 0 WHEN 'review' THEN 1 WHEN 'applied' THEN 2 "
        sql += " WHEN 'interviewing' THEN 3 WHEN 'offer' THEN 4 ELSE 5 END"
        return conn.execute(sql, [s.value for s in statuses]).fetchall()
    sql += " ORDER BY a.updated_at DESC"
    return conn.execute(sql).fetchall()


# --------------------------------------------------------------------------- #
# Scores
# --------------------------------------------------------------------------- #
def save_scores(conn: sqlite3.Connection, run_id: int, scores: list[Score]) -> None:
    for score in scores:
        conn.execute(
            """INSERT INTO offer_scores (offer_id, run_id, score, triage,
               breakdown, extracted, hard_filters, reason)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(offer_id, run_id) DO UPDATE SET
                 score=excluded.score, triage=excluded.triage,
                 breakdown=excluded.breakdown, extracted=excluded.extracted,
                 hard_filters=excluded.hard_filters, reason=excluded.reason""",
            (
                score.offer_id,
                run_id,
                score.total,
                score.triage.value,
                json.dumps(
                    {k: {"value": v.value, "weight": v.weight, "evidence": v.evidence} for k, v in score.breakdown.items()},
                    ensure_ascii=False,
                ),
                json.dumps(score.extracted, ensure_ascii=False),
                json.dumps(score.hard_filters, ensure_ascii=False),
                score.reason,
            ),
        )
    conn.commit()


def scores_for_run(conn: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
    sql = """
        SELECT s.offer_id, s.run_id, s.score, s.triage, s.breakdown, s.extracted,
               s.hard_filters, s.reason,
               o.title, o.company, o.location, o.apply_url, o.url,
               (SELECT GROUP_CONCAT(f.family) FROM offer_families f WHERE f.offer_id = o.id) AS family
        FROM offer_scores s JOIN offers o ON o.id = s.offer_id
        WHERE s.run_id = ?
        ORDER BY s.score DESC
    """
    return conn.execute(sql, (run_id,)).fetchall()


# --------------------------------------------------------------------------- #
# CV variants
# --------------------------------------------------------------------------- #
def save_cv_variant(
    conn: sqlite3.Connection, family: str, content: str, job_title: str = ""
) -> int:
    cur = conn.execute(
        "INSERT INTO cv_variants (family, job_title, content, created_at) VALUES (?,?,?,?)",
        (family, job_title, content, _now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_cv_variants(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM cv_variants ORDER BY created_at DESC"
    ).fetchall()
