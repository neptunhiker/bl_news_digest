"""Tests for Slack Block Kit renderer and posting client."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from bl_news_digest.db import init_database, get_connection
from bl_news_digest.render.slack_blocks import (
    render_blocks,
    render_fallback_text,
    blocks_to_json,
)
from bl_news_digest.render.slack_client import (
    create_digest_run,
    fetch_digest_items,
    finish_digest_run,
    post_digest,
)
from bl_news_digest.ai.schemas import ItemReview


# --- fixtures ---

SAMPLE_REVIEW = ItemReview(
    decision="include",
    topic_type="AVGS regulation",
    relevance_score=9,
    beginnerluft_fit_score=8,
    actionability_score=7,
    business_impact_score=8,
    urgency_score=6,
    confidence=9,
    summary="Neue AVGS-Regelungen treten in Kraft.",
    why_relevant="Betrifft Gutscheinbudgets direkt.",
    recommended_actions=["Bundesanzeiger beobachten", "Interne Richtlinien anpassen"],
)

SAMPLE_ITEM: dict = {
    "item_id": 1,
    "title": "AVGS-Änderung beschlossen",
    "url_canonical": "https://bmas.de/avgs-neu",
    "source_domain": "bmas.de",
    "summary": "Neue AVGS-Regelungen treten in Kraft.",
    "why_relevant": "Betrifft Gutscheinbudgets direkt.",
    "recommended_actions": ["Bundesanzeiger beobachten"],
    "relevance_score": 9,
}


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


# --- render_blocks tests ---

def test_render_blocks_has_header():
    blocks = render_blocks([SAMPLE_ITEM], digest_date=date(2026, 4, 19))
    types = [b["type"] for b in blocks]
    assert "header" in types


def test_render_blocks_header_text():
    blocks = render_blocks([SAMPLE_ITEM], digest_date=date(2026, 4, 19))
    header = next(b for b in blocks if b["type"] == "header")
    assert "2026" in header["text"]["text"]
    assert "News" in header["text"]["text"]


def test_render_blocks_contains_item_title():
    blocks = render_blocks([SAMPLE_ITEM], digest_date=date(2026, 4, 19))
    all_text = json.dumps(blocks, ensure_ascii=False)
    assert "AVGS-Änderung beschlossen" in all_text


def test_render_blocks_contains_url_link():
    blocks = render_blocks([SAMPLE_ITEM], digest_date=date(2026, 4, 19))
    all_text = json.dumps(blocks)
    assert "https://bmas.de/avgs-neu" in all_text


def test_render_blocks_empty_items():
    blocks = render_blocks([], digest_date=date(2026, 4, 19))
    # Should still have header, stats context, divider, footer at minimum
    assert len(blocks) >= 3


def test_render_fallback_text():
    text = render_fallback_text([SAMPLE_ITEM], digest_date=date(2026, 4, 19))
    assert "AVGS-Digest" in text
    assert "AVGS-Änderung beschlossen" in text
    assert "https://bmas.de/avgs-neu" in text


def test_blocks_to_json_is_valid_json():
    blocks = render_blocks([SAMPLE_ITEM], digest_date=date(2026, 4, 19))
    serialised = blocks_to_json(blocks)
    parsed = json.loads(serialised)
    assert isinstance(parsed, list)


# --- digest_run DB tests ---

def test_create_digest_run_returns_id(db_conn):
    run_id = create_digest_run(db_conn, "2026-04-19")
    assert isinstance(run_id, int)
    assert run_id > 0


def test_create_digest_run_idempotent(db_conn):
    id1 = create_digest_run(db_conn, "2026-04-19")
    id2 = create_digest_run(db_conn, "2026-04-19")
    assert id1 == id2


def test_finish_digest_run_updates_status(db_conn):
    run_id = create_digest_run(db_conn, "2026-04-19")
    finish_digest_run(db_conn, run_id, status="ok", scanned=10, selected=3)
    row = db_conn.execute("SELECT status, scanned_count FROM digest_runs WHERE id=?", (run_id,)).fetchone()
    assert row["status"] == "ok"
    assert row["scanned_count"] == 10


# --- fetch_digest_items tests ---

def test_fetch_digest_items_combines_data(db_conn):
    cur = db_conn.execute(
        """
        INSERT INTO normalized_items
            (source_id, source_domain, url_original, url_canonical,
             title, summary, content_text, published_at, discovered_at,
             content_hash, rule_score, status)
        VALUES ('bmas_rss', 'bmas.de', 'https://bmas.de/x', 'https://bmas.de/x',
                'AVGS Test', 'Summary text', '', datetime('now'), datetime('now'),
                'hash_x', 1, 'shortlisted')
        """
    )
    db_conn.commit()
    item_id = cur.lastrowid

    items = fetch_digest_items(db_conn, [(item_id, SAMPLE_REVIEW)])
    assert len(items) == 1
    assert items[0]["title"] == "AVGS Test"
    assert items[0]["why_relevant"] == "Betrifft Gutscheinbudgets direkt."
    assert items[0]["recommended_actions"] == ["Bundesanzeiger beobachten", "Interne Richtlinien anpassen"]


# --- post_digest tests ---

def test_post_digest_dry_run_does_not_call_slack(db_conn):
    run_id = create_digest_run(db_conn, "2026-04-19")
    with patch("bl_news_digest.render.slack_client.get_slack_client") as mock_client:
        ts = post_digest(
            [SAMPLE_ITEM], db_conn,
            channel_id="C123", token="xoxb-test",
            digest_run_id=run_id, dry_run=True,
        )
    mock_client.assert_not_called()
    assert ts is None
    # Payload should still be persisted
    row = db_conn.execute("SELECT posted_at FROM outbound_messages WHERE digest_run_id=?", (run_id,)).fetchone()
    assert row is not None
    assert row["posted_at"] is None


def test_post_digest_live_calls_slack_and_persists_ts(db_conn):
    run_id = create_digest_run(db_conn, "2026-04-19")

    mock_wc = MagicMock()
    mock_wc.chat_postMessage.return_value = {"ts": "1234567890.123"}

    with patch("bl_news_digest.render.slack_client.get_slack_client", return_value=mock_wc):
        ts = post_digest(
            [SAMPLE_ITEM], db_conn,
            channel_id="C123", token="xoxb-test",
            digest_run_id=run_id, dry_run=False,
        )

    assert ts == "1234567890.123"
    mock_wc.chat_postMessage.assert_called_once()
    row = db_conn.execute(
        "SELECT provider_message_id, posted_at FROM outbound_messages WHERE digest_run_id=?",
        (run_id,),
    ).fetchone()
    assert row["provider_message_id"] == "1234567890.123"
    assert row["posted_at"] is not None


def test_post_digest_empty_items_skips_live_slack_post(db_conn):
    run_id = create_digest_run(db_conn, "2026-04-19")

    mock_wc = MagicMock()

    with patch("bl_news_digest.render.slack_client.get_slack_client", return_value=mock_wc):
        ts = post_digest(
            [], db_conn,
            channel_id="C123", token="xoxb-test",
            digest_run_id=run_id, dry_run=False,
        )

    assert ts is None
    mock_wc.chat_postMessage.assert_not_called()
    row = db_conn.execute(
        "SELECT COUNT(*) AS count FROM outbound_messages WHERE digest_run_id=?",
        (run_id,),
    ).fetchone()
    assert row["count"] == 0
