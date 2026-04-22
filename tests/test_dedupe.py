"""Tests for deduplication."""

from __future__ import annotations

from bl_news_digest.db import init_database, get_connection
from bl_news_digest.ingest.dedupe import deduplicate


def _seed_source(conn):
    conn.execute(
        """
        INSERT OR IGNORE INTO sources
            (id, family, priority, method, url, enabled, cadence_minutes, parser)
        VALUES ('bmas_rss', 'bmas', 1, 'rss', 'https://www.bmas.de/', 1, 1440, 'rss_parser')
        """
    )
    conn.commit()


def _insert_item(conn, id_: int, title: str, url: str, content_hash: str):
    conn.execute(
        """
        INSERT INTO normalized_items
            (id, source_id, url_original, url_canonical, source_domain,
             title, summary, content_text, published_at, discovered_at,
             content_hash, rule_score, status)
        VALUES (?, 'bmas_rss', ?, ?, 'bmas.de', ?, '', '', NULL,
                '2026-04-19T08:00:00+00:00', ?, 0, 'new')
        """,
        (id_, url, url, title, content_hash),
    )
    conn.commit()


def test_deduplicate_rejects_near_duplicate_titles(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_database(db_path)
    conn = get_connection(db_path)
    _seed_source(conn)

    _insert_item(conn, 1, "AVGS Regelung wird geändert 2026", "https://a.de/1", "hash1")
    _insert_item(conn, 2, "AVGS Regelung wird geändert 2026 neu", "https://a.de/2", "hash2")
    _insert_item(conn, 3, "Völlig anderes Thema: Klimawandel", "https://a.de/3", "hash3")

    rejected = deduplicate(conn)

    assert rejected == 1
    statuses = {
        r["id"]: r["status"]
        for r in conn.execute("SELECT id, status FROM normalized_items").fetchall()
    }
    assert statuses[1] == "new"       # kept
    assert statuses[2] == "rejected"  # near-dup of 1
    assert statuses[3] == "new"       # different topic, kept
    conn.close()


def test_deduplicate_keeps_unique_items(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_database(db_path)
    conn = get_connection(db_path)
    _seed_source(conn)

    _insert_item(conn, 1, "AVGS Neuregelung", "https://a.de/1", "hash1")
    _insert_item(conn, 2, "Jobcenter Statistik Q1", "https://a.de/2", "hash2")
    _insert_item(conn, 3, "IAB Forschungsbericht Arbeitsmarkt", "https://a.de/3", "hash3")

    rejected = deduplicate(conn)

    assert rejected == 0
    conn.close()


def _insert_selected_item(conn, id_: int, title: str, url: str, content_hash: str, discovered_at: str = "2026-04-20T08:00:00+00:00"):
    """Insert an item that was already selected (posted) in a previous digest run."""
    conn.execute(
        """
        INSERT INTO normalized_items
            (id, source_id, url_original, url_canonical, source_domain,
             title, summary, content_text, published_at, discovered_at,
             content_hash, rule_score, status)
        VALUES (?, 'bmas_rss', ?, ?, 'bmas.de', ?, '', '', NULL,
                ?, ?, 0, 'selected')
        """,
        (id_, url, url, title, discovered_at, content_hash),
    )
    conn.commit()


def test_deduplicate_rejects_cross_run_near_duplicate(tmp_path):
    """A new item that is nearly identical to a previously selected item should be rejected."""
    db_path = str(tmp_path / "test.db")
    init_database(db_path)
    conn = get_connection(db_path)
    _seed_source(conn)

    # Simulate an article posted yesterday (status='selected')
    _insert_selected_item(conn, 1, "AVGS Regelung wird geändert 2026", "https://a.de/1", "hashA")

    # Today a near-duplicate arrives with a slightly different URL (new status)
    _insert_item(conn, 2, "AVGS Regelung wird geändert 2026 aktuell", "https://b.de/1", "hashB")
    # A genuinely new article should not be affected
    _insert_item(conn, 3, "Völlig anderes Thema: Klimawandel", "https://a.de/3", "hashC")

    rejected = deduplicate(conn)

    assert rejected == 1
    statuses = {
        r["id"]: r["status"]
        for r in conn.execute("SELECT id, status FROM normalized_items").fetchall()
    }
    assert statuses[1] == "selected"  # unchanged
    assert statuses[2] == "rejected"  # near-dup of previously selected item
    assert statuses[3] == "new"       # different topic, kept
    conn.close()


def test_deduplicate_ignores_old_selected_items_beyond_lookback(tmp_path):
    """Items selected longer ago than the lookback window should not block new items."""
    from bl_news_digest.ingest import dedupe as dedupe_mod

    db_path = str(tmp_path / "test.db")
    init_database(db_path)
    conn = get_connection(db_path)
    _seed_source(conn)

    # An article selected 91 days ago — beyond the default 90-day lookback
    _insert_selected_item(
        conn, 1, "AVGS Regelung wird geändert 2026", "https://a.de/1", "hashA",
        discovered_at="2026-01-20T08:00:00+00:00",
    )

    # A near-duplicate arriving today — should NOT be rejected because the anchor is too old
    _insert_item(conn, 2, "AVGS Regelung wird geändert 2026 aktuell", "https://b.de/1", "hashB")

    original_lookback = dedupe_mod._HISTORY_LOOKBACK_DAYS
    dedupe_mod._HISTORY_LOOKBACK_DAYS = 90  # ensure default is used
    try:
        rejected = deduplicate(conn)
    finally:
        dedupe_mod._HISTORY_LOOKBACK_DAYS = original_lookback

    assert rejected == 0
    conn.close()
