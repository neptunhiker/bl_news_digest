from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sources (
    id               TEXT PRIMARY KEY,
    family           TEXT NOT NULL,
    priority         INTEGER NOT NULL DEFAULT 1,
    method           TEXT NOT NULL,
    url              TEXT NOT NULL,
    enabled          INTEGER NOT NULL DEFAULT 1,
    cadence_minutes  INTEGER NOT NULL DEFAULT 1440,
    parser           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fetch_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    status       TEXT NOT NULL DEFAULT 'pending',
    items_seen   INTEGER DEFAULT 0,
    items_new    INTEGER DEFAULT 0,
    error_text   TEXT,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS raw_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id     TEXT NOT NULL,
    fetch_run_id  INTEGER NOT NULL,
    url_original  TEXT NOT NULL,
    external_id   TEXT,
    raw_payload   TEXT NOT NULL,
    raw_hash      TEXT NOT NULL,
    stored_at     TEXT NOT NULL,
    FOREIGN KEY (source_id)    REFERENCES sources(id),
    FOREIGN KEY (fetch_run_id) REFERENCES fetch_runs(id)
);

CREATE TABLE IF NOT EXISTS normalized_items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id      TEXT NOT NULL,
    url_original   TEXT NOT NULL,
    url_canonical  TEXT NOT NULL,
    source_domain  TEXT NOT NULL,
    title          TEXT NOT NULL,
    summary        TEXT,
    content_text   TEXT,
    published_at   TEXT,
    discovered_at  TEXT NOT NULL,
    content_hash   TEXT NOT NULL,
    rule_score     INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'new',
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_normalized_url_canonical
    ON normalized_items(url_canonical);
CREATE INDEX IF NOT EXISTS idx_normalized_content_hash
    ON normalized_items(content_hash);
CREATE INDEX IF NOT EXISTS idx_normalized_status
    ON normalized_items(status);

CREATE TABLE IF NOT EXISTS item_reviews (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id                  INTEGER NOT NULL,
    content_hash             TEXT NOT NULL,
    decision                 TEXT NOT NULL,
    topic_type               TEXT,
    relevance_score          REAL,
    beginnerluft_fit_score   REAL,
    actionability_score      REAL,
    business_impact_score    REAL,
    urgency_score            REAL,
    confidence               REAL,
    summary                  TEXT,
    why_relevant             TEXT,
    recommended_actions      TEXT,
    review_json              TEXT NOT NULL,
    reviewed_at              TEXT NOT NULL,
    cache_hit                INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (item_id) REFERENCES normalized_items(id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_item_id ON item_reviews(item_id);

CREATE TABLE IF NOT EXISTS digest_runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    digest_date      TEXT NOT NULL,
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    status           TEXT NOT NULL DEFAULT 'pending',
    scanned_count    INTEGER DEFAULT 0,
    candidate_count  INTEGER DEFAULT 0,
    reviewed_count   INTEGER DEFAULT 0,
    selected_count   INTEGER DEFAULT 0,
    editor_note      TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_digest_runs_date ON digest_runs(digest_date);

CREATE TABLE IF NOT EXISTS digest_items (
    digest_run_id       INTEGER NOT NULL,
    item_id             INTEGER NOT NULL,
    rank                INTEGER NOT NULL,
    final_score         REAL,
    why_relevant        TEXT,
    recommended_action  TEXT,
    PRIMARY KEY (digest_run_id, item_id),
    FOREIGN KEY (digest_run_id) REFERENCES digest_runs(id),
    FOREIGN KEY (item_id)       REFERENCES normalized_items(id)
);

CREATE TABLE IF NOT EXISTS outbound_messages (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    digest_run_id       INTEGER NOT NULL,
    channel_id          TEXT NOT NULL,
    provider            TEXT NOT NULL DEFAULT 'slack',
    provider_message_id TEXT,
    payload_json        TEXT NOT NULL,
    posted_at           TEXT,
    FOREIGN KEY (digest_run_id) REFERENCES digest_runs(id)
);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: str) -> None:
    """Create all tables and indexes if they do not already exist."""
    logger.info("Initialising database at %s", db_path)
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        logger.info("Database initialised successfully")
    finally:
        conn.close()
