"""RSS fetcher — fetches all enabled RSS sources and persists raw items."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from bl_news_digest.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = 30  # seconds


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _fetch_url(url: str, user_agent: str) -> str:
    headers = {"User-Agent": user_agent}
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        return response.text


def fetch_source(source: dict, conn) -> tuple[int, int]:
    """Fetch one RSS source, persist raw items, return (items_seen, items_new)."""
    settings = get_settings()
    source_id = source["id"]
    url = source["url"]

    started_at = _now_iso()
    cursor = conn.cursor()

    # Open a fetch_run record
    cursor.execute(
        """
        INSERT INTO fetch_runs (source_id, started_at, status)
        VALUES (?, ?, 'running')
        """,
        (source_id, started_at),
    )
    fetch_run_id = cursor.lastrowid
    conn.commit()

    items_seen = 0
    items_new = 0
    error_text = None

    try:
        logger.info("Fetching %s from %s", source_id, url)
        raw_content = _fetch_url(url, settings.http_user_agent)
        feed = feedparser.parse(raw_content)

        for entry in feed.entries:
            items_seen += 1
            entry_url = getattr(entry, "link", "") or ""
            entry_id = getattr(entry, "id", entry_url) or entry_url
            payload = str(dict(entry))
            raw_hash = _hash(payload)

            # Skip exact raw duplicates already stored
            row = cursor.execute(
                "SELECT id FROM raw_items WHERE raw_hash = ?", (raw_hash,)
            ).fetchone()
            if row:
                continue

            cursor.execute(
                """
                INSERT INTO raw_items
                    (source_id, fetch_run_id, url_original, external_id,
                     raw_payload, raw_hash, stored_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    fetch_run_id,
                    entry_url,
                    entry_id,
                    payload,
                    raw_hash,
                    _now_iso(),
                ),
            )
            items_new += 1

        conn.commit()
        logger.info("%s: seen=%d new=%d", source_id, items_seen, items_new)

    except Exception as exc:
        error_text = str(exc)
        logger.error("Error fetching %s: %s", source_id, error_text)
        conn.rollback()

    finally:
        cursor.execute(
            """
            UPDATE fetch_runs
            SET finished_at = ?, status = ?, items_seen = ?, items_new = ?, error_text = ?
            WHERE id = ?
            """,
            (
                _now_iso(),
                "error" if error_text else "ok",
                items_seen,
                items_new,
                error_text,
                fetch_run_id,
            ),
        )
        conn.commit()

    return items_seen, items_new


def fetch_all_sources(sources: list[dict], conn) -> dict[str, tuple[int, int]]:
    """Fetch all enabled sources. Returns {source_id: (seen, new)}."""
    results = {}
    for source in sources:
        if not source.get("enabled", False):
            logger.info("Skipping disabled source: %s", source["id"])
            continue
        results[source["id"]] = fetch_source(source, conn)
    return results

