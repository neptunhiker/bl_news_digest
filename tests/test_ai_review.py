"""Tests for AI review pipeline and ranking."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from bl_news_digest.ai.rank import select_top_n
from bl_news_digest.ai.review import review_item, review_all_shortlisted
from bl_news_digest.ai.schemas import ItemReview
from bl_news_digest.db import init_database, get_connection


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
    summary="New AVGS rules announced.",
    why_relevant="Directly affects coaching voucher budgets.",
    recommended_actions=["Monitor official gazette", "Update internal guidance"],
)


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


def _insert_shortlisted(conn, slug: str, domain: str = "bmas.de") -> int:
    cur = conn.execute(
        """
        INSERT INTO normalized_items
            (source_id, source_domain, url_original, url_canonical,
             title, summary, content_text, published_at, discovered_at,
             content_hash, rule_score, status)
        VALUES ('bmas_rss', ?, ?, ?,
                'AVGS Neuerung', 'Es gibt neue AVGS Regelungen.', '',
                datetime('now'), datetime('now'), ?, 1, 'shortlisted')
        """,
        (domain, f"https://{domain}/{slug}", f"https://{domain}/{slug}", f"hash_{slug}"),
    )
    conn.commit()
    return cur.lastrowid


# --- schema tests ---

def test_item_review_schema_valid():
    data = SAMPLE_REVIEW.model_dump()
    assert data["decision"] == "include"
    assert 1 <= data["relevance_score"] <= 10


def test_item_review_schema_rejects_out_of_range():
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        ItemReview(
            decision="include",
            topic_type="x",
            relevance_score=11,  # invalid
            beginnerluft_fit_score=5,
            actionability_score=5,
            business_impact_score=5,
            urgency_score=5,
            confidence=5,
            summary="x",
            why_relevant="x",
            recommended_actions=[],
        )


# --- review_item tests ---

def test_review_item_calls_api_and_persists(db_conn, monkeypatch):
    item_id = _insert_shortlisted(db_conn, "item1")

    with patch("bl_news_digest.ai.review.parse_structured", return_value=SAMPLE_REVIEW):
        result = review_item(item_id, db_conn, dry_run=False)

    assert result is not None
    assert result.decision == "include"

    row = db_conn.execute(
        "SELECT decision, relevance_score, cache_hit FROM item_reviews WHERE item_id=?",
        (item_id,),
    ).fetchone()
    assert row["decision"] == "include"
    assert row["relevance_score"] == 9
    assert row["cache_hit"] == 0


def test_review_item_dry_run_skips_api(db_conn):
    item_id = _insert_shortlisted(db_conn, "item2")

    with patch("bl_news_digest.ai.review.parse_structured") as mock_api:
        result = review_item(item_id, db_conn, dry_run=True)

    mock_api.assert_not_called()
    assert result is None


def test_review_item_uses_cache_on_second_call(db_conn, monkeypatch):
    monkeypatch.setenv("AI_REVIEW_CACHE_ENABLED", "true")
    item_id = _insert_shortlisted(db_conn, "item3")

    with patch("bl_news_digest.ai.review.parse_structured", return_value=SAMPLE_REVIEW) as mock_api:
        # First call — should hit the API
        review_item(item_id, db_conn, dry_run=False)
        assert mock_api.call_count == 1

        # Insert a second item with same content_hash to simulate cache scenario
        cur = db_conn.execute(
            """
            INSERT INTO normalized_items
                (source_id, source_domain, url_original, url_canonical,
                 title, summary, content_text, published_at, discovered_at,
                 content_hash, rule_score, status)
            VALUES ('bmas_rss', 'bmas.de', 'https://bmas.de/item3b', 'https://bmas.de/item3b',
                    'Duplicate', '', '', datetime('now'), datetime('now'),
                    'hash_item3', 1, 'shortlisted')
            """
        )
        db_conn.commit()
        item_id2 = cur.lastrowid

        # Second call with same hash — should use cache
        result = review_item(item_id2, db_conn, dry_run=False)
        assert mock_api.call_count == 1  # still 1 — no new API call
        assert result is not None
        assert result.decision == "include"


# --- ranking tests ---

def test_select_top_n_filters_excludes(db_conn):
    item_id = _insert_shortlisted(db_conn, "excl1")
    excluded_review = ItemReview(
        decision="exclude",
        topic_type="Unrelated",
        relevance_score=2,
        beginnerluft_fit_score=2,
        actionability_score=2,
        business_impact_score=2,
        urgency_score=2,
        confidence=8,
        summary="Not relevant.",
        why_relevant="Not relevant to BeginnerLuft.",
        recommended_actions=[],
    )
    result = select_top_n([(item_id, excluded_review)], db_conn, top_n=5)
    assert result == []


def test_select_top_n_enforces_domain_cap(db_conn):
    # Insert 3 items from same domain
    ids = [_insert_shortlisted(db_conn, f"d{i}", domain="bmas.de") for i in range(3)]
    reviews = [(i, SAMPLE_REVIEW) for i in ids]
    result = select_top_n(reviews, db_conn, top_n=5)
    assert len(result) == 2  # MAX_PER_DOMAIN=2


def test_select_top_n_returns_correct_count(db_conn):
    id1 = _insert_shortlisted(db_conn, "r1", domain="bmas.de")
    id2 = _insert_shortlisted(db_conn, "r2", domain="bundestag.de")
    id3 = _insert_shortlisted(db_conn, "r3", domain="iab.de")
    reviews = [(id1, SAMPLE_REVIEW), (id2, SAMPLE_REVIEW), (id3, SAMPLE_REVIEW)]
    result = select_top_n(reviews, db_conn, top_n=2)
    assert len(result) == 2
