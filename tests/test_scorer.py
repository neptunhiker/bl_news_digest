"""Tests for rule-based keyword scorer."""

from __future__ import annotations

import pytest

from bl_news_digest.db import init_database, get_connection
from bl_news_digest.rules.scorer import apply_scores, score_item


# --- unit tests for score_item ---


def test_score_item_passes_on_avgs_title():
    score, status = score_item("Neue AVGS-Regelung", "", "bmas.de")
    assert score == 1
    assert status == "shortlisted"


def test_score_item_passes_on_azav_in_summary():
    score, status = score_item("Meldung", "AZAV-Akkreditierung verlängert", "iab.de")
    assert score == 1
    assert status == "shortlisted"


def test_score_item_rejects_noise():
    score, status = score_item("Wetter heute sonnig", "Temperaturen steigen", "bmas.de")
    assert score == 0
    assert status == "rejected"


def test_score_item_blocks_beginnerluft_domain():
    # Even with a matching keyword the domain block takes priority
    score, status = score_item("AVGS Neuigkeiten", "azav info", "beginnerluft.de")
    assert score == 0
    assert status == "rejected"


def test_score_item_case_insensitive():
    score, status = score_item("BILDUNGSTRÄGER in Deutschland", "", "iab.de")
    assert score == 1
    assert status == "shortlisted"


def test_score_item_traegerzulassung():
    score, status = score_item("Trägerzulassung wird vereinfacht", "", "bmas.de")
    assert score == 1
    assert status == "shortlisted"


# --- integration tests for apply_scores ---


@pytest.fixture()
def db_conn(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    db_path = str(tmp_path / "test.db")
    init_database(db_path)
    conn = get_connection(db_path)
    conn.execute(
        """
        INSERT INTO sources (id, family, priority, method, url, enabled, cadence_minutes, parser)
        VALUES ('bmas_rss', 'bmas', 1, 'rss', 'https://bmas.de/rss', 1, 1440, 'rss_parser')
        """
    )
    conn.commit()
    yield conn
    conn.close()


def _insert_item(conn, slug: str, title: str, summary: str, domain: str = "bmas.de") -> int:
    cur = conn.execute(
        """
        INSERT INTO normalized_items
            (source_id, source_domain, url_original, url_canonical,
             title, summary, content_text, published_at, discovered_at,
             content_hash, rule_score, status)
        VALUES ('bmas_rss', ?, ?, ?,
                ?, ?, '', datetime('now'), datetime('now'),
                ?, 0, 'new')
        """,
        (domain, f"https://{domain}/{slug}", f"https://{domain}/{slug}",
         title, summary, f"hash_{slug}"),
    )
    conn.commit()
    return cur.lastrowid


def test_apply_scores_shortlists_keyword_match(db_conn):
    rowid = _insert_item(db_conn, "item1", "AVGS Neuerung", "Details", "bmas.de")
    shortlisted, rejected = apply_scores(db_conn)
    assert shortlisted == 1
    assert rejected == 0
    row = db_conn.execute("SELECT status, rule_score FROM normalized_items WHERE id=?", (rowid,)).fetchone()
    assert row["status"] == "shortlisted"
    assert row["rule_score"] == 1


def test_apply_scores_rejects_noise(db_conn):
    rowid = _insert_item(db_conn, "item2", "Wetter Bericht", "Sonnig", "bmas.de")
    shortlisted, rejected = apply_scores(db_conn)
    assert shortlisted == 0
    assert rejected == 1
    row = db_conn.execute("SELECT status FROM normalized_items WHERE id=?", (rowid,)).fetchone()
    assert row["status"] == "rejected"


def test_apply_scores_skips_non_new_items(db_conn):
    rowid = _insert_item(db_conn, "item3", "AVGS Info", "", "bmas.de")
    db_conn.execute("UPDATE normalized_items SET status='shortlisted' WHERE id=?", (rowid,))
    db_conn.commit()
    shortlisted, rejected = apply_scores(db_conn)
    # Already shortlisted — apply_scores only processes status='new', so 0 processed
    assert shortlisted == 0
    assert rejected == 0
