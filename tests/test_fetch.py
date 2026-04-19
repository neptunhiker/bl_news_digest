"""Tests for the RSS fetcher."""

from __future__ import annotations

import pytest
import respx
import httpx

from bl_news_digest.db import init_database, get_connection
from bl_news_digest.ingest.fetch import fetch_source


BMAS_FIXTURE = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BMAS Aktuell</title>
    <link>https://www.bmas.de</link>
    <item>
      <title>Neue AVGS-Regelung veröffentlicht</title>
      <link>https://www.bmas.de/avgs-neu</link>
      <pubDate>Sun, 19 Apr 2026 08:00:00 +0000</pubDate>
      <description>Änderungen bei AVGS und Trägerzulassung</description>
    </item>
    <item>
      <title>Jobcenter Statistik Q1 2026</title>
      <link>https://www.bmas.de/statistik-q1</link>
      <pubDate>Sat, 18 Apr 2026 10:00:00 +0000</pubDate>
      <description>Arbeitslosenzahlen gesunken</description>
    </item>
  </channel>
</rss>
"""


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_database(db_path)
    conn = get_connection(db_path)
    # Seed the sources table so FK constraints on fetch_runs are satisfied
    conn.execute(
        """
        INSERT INTO sources (id, family, priority, method, url, enabled, cadence_minutes, parser)
        VALUES ('bmas_rss', 'bmas', 1, 'rss',
                'https://www.bmas.de/DE/Service/Newsletter/RSS/rss.html',
                1, 1440, 'rss_parser')
        """
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def bmas_source():
    return {
        "id": "bmas_rss",
        "enabled": True,
        "family": "bmas",
        "priority": 1,
        "method": "rss",
        "parser": "rss_parser",
        "cadence_minutes": 1440,
        "url": "https://www.bmas.de/DE/Service/Newsletter/RSS/rss.html",
    }


@respx.mock
def test_fetch_source_stores_raw_items(db_conn, bmas_source, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")

    respx.get(bmas_source["url"]).mock(
        return_value=httpx.Response(200, text=BMAS_FIXTURE)
    )

    seen, new = fetch_source(bmas_source, db_conn)

    assert seen == 2
    assert new == 2

    rows = db_conn.execute("SELECT * FROM raw_items").fetchall()
    assert len(rows) == 2
    urls = {r["url_original"] for r in rows}
    assert "https://www.bmas.de/avgs-neu" in urls


@respx.mock
def test_fetch_source_skips_duplicates(db_conn, bmas_source, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")

    respx.get(bmas_source["url"]).mock(
        return_value=httpx.Response(200, text=BMAS_FIXTURE)
    )

    fetch_source(bmas_source, db_conn)
    seen2, new2 = fetch_source(bmas_source, db_conn)

    assert seen2 == 2
    assert new2 == 0  # all already stored


@respx.mock
def test_fetch_source_records_error_on_http_failure(db_conn, bmas_source, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")

    respx.get(bmas_source["url"]).mock(
        return_value=httpx.Response(503)
    )

    seen, new = fetch_source(bmas_source, db_conn)

    assert seen == 0
    assert new == 0
    run = db_conn.execute(
        "SELECT status, error_text FROM fetch_runs WHERE source_id = 'bmas_rss'"
    ).fetchone()
    assert run["status"] == "error"
    assert run["error_text"] is not None
