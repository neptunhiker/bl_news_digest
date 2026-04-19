"""Slack posting client: posts digest blocks and persists metadata."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from bl_news_digest.render.slack_blocks import DigestItemDict, render_blocks, render_fallback_text, blocks_to_json

log = logging.getLogger(__name__)


def get_slack_client(token: str) -> WebClient:
    return WebClient(token=token)


def fetch_digest_items(
    conn: sqlite3.Connection,
    top: list[tuple[int, object]],  # list of (item_id, ItemReview)
) -> list[DigestItemDict]:
    """Join NormalizedItem DB rows with ItemReview objects for rendering."""
    from bl_news_digest.ai.schemas import ItemReview

    result: list[DigestItemDict] = []
    for item_id, review in top:
        row = conn.execute(
            "SELECT title, url_canonical, source_domain, summary FROM normalized_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if not row:
            continue
        assert isinstance(review, ItemReview)
        result.append({
            "item_id": item_id,
            "title": row["title"],
            "url_canonical": row["url_canonical"],
            "source_domain": row["source_domain"],
            "summary": row["summary"] or "",
            "why_relevant": review.why_relevant,
            "recommended_actions": review.recommended_actions,
            "relevance_score": review.relevance_score,
        })
    return result


def post_digest(
    items: list[DigestItemDict],
    conn: sqlite3.Connection,
    *,
    channel_id: str,
    token: str,
    digest_run_id: int,
    dry_run: bool = False,
    scanned: int = 0,
    shortlisted: int = 0,
) -> str | None:
    """Render the digest and post to Slack (or print in dry-run mode).

    Returns the Slack message timestamp (`ts`) on success, None otherwise.
    Persists the payload and response metadata to `outbound_messages`.
    """
    blocks = render_blocks(items, scanned=scanned, shortlisted=shortlisted)
    fallback = render_fallback_text(items)
    payload_json = blocks_to_json(blocks)

    if dry_run:
        log.info("Dry run — Slack payload (not posted):\n%s", payload_json)
        _persist_outbound(conn, digest_run_id, channel_id, payload_json, posted_at=None)
        return None

    client = get_slack_client(token)
    try:
        response = client.chat_postMessage(
            channel=channel_id,
            text=fallback,
            blocks=blocks,
        )
        ts: str = response["ts"]
        log.info("Posted digest to Slack channel %s (ts=%s)", channel_id, ts)
        _persist_outbound(conn, digest_run_id, channel_id, payload_json, posted_at=datetime.now(timezone.utc).isoformat(), provider_message_id=ts)
        return ts
    except SlackApiError as exc:
        log.error("Slack API error: %s", exc.response["error"])
        _persist_outbound(conn, digest_run_id, channel_id, payload_json, posted_at=None)
        return None


def _persist_outbound(
    conn: sqlite3.Connection,
    digest_run_id: int,
    channel_id: str,
    payload_json: str,
    *,
    posted_at: str | None,
    provider_message_id: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO outbound_messages
            (digest_run_id, channel_id, provider, provider_message_id, payload_json, posted_at)
        VALUES (?, ?, 'slack', ?, ?, ?)
        """,
        (digest_run_id, channel_id, provider_message_id, payload_json, posted_at),
    )
    conn.commit()


def create_digest_run(conn: sqlite3.Connection, digest_date: str) -> int:
    """Insert a digest_run row and return its id."""
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO digest_runs (digest_date, started_at, status)
        VALUES (?, ?, 'pending')
        """,
        (digest_date, now),
    )
    conn.commit()
    if cur.lastrowid:
        return cur.lastrowid
    # Already exists for today — return existing id
    row = conn.execute(
        "SELECT id FROM digest_runs WHERE digest_date = ?", (digest_date,)
    ).fetchone()
    return row["id"]


def finish_digest_run(
    conn: sqlite3.Connection,
    digest_run_id: int,
    *,
    status: str,
    scanned: int = 0,
    candidate: int = 0,
    reviewed: int = 0,
    selected: int = 0,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        UPDATE digest_runs
        SET finished_at=?, status=?, scanned_count=?, candidate_count=?,
            reviewed_count=?, selected_count=?
        WHERE id=?
        """,
        (now, status, scanned, candidate, reviewed, selected, digest_run_id),
    )
    conn.commit()

