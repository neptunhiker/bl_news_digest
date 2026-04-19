"""AI review pipeline: sends shortlisted items to the model and persists results.

Cache logic:
  - Before calling the API, check item_reviews for a row with matching content_hash.
  - If found and ai_review_cache_enabled=True, reuse the stored review (no API call).
  - Otherwise call the API and store the result.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone

import openai

from bl_news_digest.ai.client import get_client, parse_structured
from bl_news_digest.ai.prompts import SYSTEM_PROMPT
from bl_news_digest.ai.schemas import ItemReview
from bl_news_digest.config import get_settings

log = logging.getLogger(__name__)


def _user_message(title: str, summary: str, url: str, source_domain: str) -> str:
    return (
        f"Source: {source_domain}\n"
        f"URL: {url}\n"
        f"Title: {title}\n"
        f"Summary: {summary or '(no summary)'}\n"
    )


def review_item(
    item_id: int,
    conn: sqlite3.Connection,
    *,
    dry_run: bool = False,
) -> ItemReview | None:
    """Review a single normalized item and persist the result to item_reviews.

    Returns the ItemReview on success, None on failure.
    Skips the API call in dry_run mode (returns None and marks as skipped).
    """
    settings = get_settings()
    row = conn.execute(
        "SELECT title, summary, url_canonical, source_domain, content_hash FROM normalized_items WHERE id = ?",
        (item_id,),
    ).fetchone()
    if not row:
        log.warning("review_item: item %d not found", item_id)
        return None

    title, summary, url, domain, content_hash = (
        row["title"], row["summary"], row["url_canonical"], row["source_domain"], row["content_hash"]
    )

    # Cache check
    if settings.ai_review_cache_enabled:
        cached = conn.execute(
            "SELECT review_json FROM item_reviews WHERE content_hash = ? LIMIT 1",
            (content_hash,),
        ).fetchone()
        if cached:
            log.debug("Cache hit for content_hash=%s (item %d)", content_hash, item_id)
            review = ItemReview.model_validate_json(cached["review_json"])
            _persist_review(conn, item_id, content_hash, review, cached=True)
            return review

    if dry_run:
        log.info("Dry run: skipping AI call for item %d (%s)", item_id, title)
        return None

    # API call
    client = get_client()
    try:
        review: ItemReview = parse_structured(
            client,
            model=settings.openai_model,
            system_prompt=SYSTEM_PROMPT,
            user_message=_user_message(title, summary or "", url, domain),
            schema=ItemReview,
        )
    except openai.OpenAIError as exc:
        log.error("OpenAI error reviewing item %d: %s", item_id, exc)
        conn.execute(
            "UPDATE normalized_items SET status='error' WHERE id=?", (item_id,)
        )
        conn.commit()
        return None

    _persist_review(conn, item_id, content_hash, review, cached=False)
    return review


def _persist_review(
    conn: sqlite3.Connection,
    item_id: int,
    content_hash: str,
    review: ItemReview,
    *,
    cached: bool,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT OR REPLACE INTO item_reviews
            (item_id, content_hash, decision, topic_type,
             relevance_score, beginnerluft_fit_score, actionability_score,
             business_impact_score, urgency_score, confidence,
             summary, why_relevant, recommended_actions,
             review_json, reviewed_at, cache_hit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item_id, content_hash,
            review.decision, review.topic_type,
            review.relevance_score, review.beginnerluft_fit_score,
            review.actionability_score, review.business_impact_score,
            review.urgency_score, review.confidence,
            review.summary, review.why_relevant,
            json.dumps(review.recommended_actions, ensure_ascii=False),
            review.model_dump_json(),
            now, int(cached),
        ),
    )
    conn.commit()
    log.debug("Persisted review for item %d (decision=%s, relevance=%d)", item_id, review.decision, review.relevance_score)


def review_all_shortlisted(conn: sqlite3.Connection, *, dry_run: bool = False) -> list[tuple[int, ItemReview]]:
    """Review all shortlisted items. Returns list of (item_id, review) for successful reviews."""
    rows = conn.execute(
        "SELECT id FROM normalized_items WHERE status = 'shortlisted'"
    ).fetchall()

    results: list[tuple[int, ItemReview]] = []
    for row in rows:
        item_id = row["id"]
        review = review_item(item_id, conn, dry_run=dry_run)
        if review is not None:
            results.append((item_id, review))

    log.info("Reviewed %d/%d shortlisted items", len(results), len(rows))
    return results
