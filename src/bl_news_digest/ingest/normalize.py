"""Normalizer — converts raw RSS feed entries into NormalizedItems and persists them."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl

logger = logging.getLogger(__name__)

# Query params that carry no semantic meaning and should be stripped
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "referrer",
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_url(url: str) -> str:
    """Strip tracking params and normalise to lowercase scheme+host."""
    if not url:
        return url
    try:
        parsed = urlparse(url)
        clean_params = urlencode(
            [(k, v) for k, v in parse_qsl(parsed.query) if k not in _TRACKING_PARAMS]
        )
        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            clean_params,
            "",  # strip fragment
        ))
    except Exception:
        return url


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def _parse_date(entry: dict) -> str | None:
    """Try to extract a publication date from a feedparser entry dict."""
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return None


def _clean_text(text: str | None) -> str:
    """Strip HTML tags and collapse whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_raw_item(raw_payload: str, source_id: str, url_original: str) -> dict | None:
    """
    Parse a raw feedparser entry (stored as str(dict)) into a normalised dict.
    Returns None if the entry cannot be normalised (e.g. missing title and URL).
    """
    try:
        entry = json.loads(raw_payload)
    except Exception as exc:
        logger.warning("Could not parse raw_payload for %s: %s", source_id, exc)
        return None

    title = _clean_text(entry.get("title", ""))
    link = entry.get("link", url_original) or url_original
    summary = _clean_text(entry.get("summary", "") or entry.get("description", ""))

    if not title and not link:
        logger.debug("Skipping entry with no title and no link from %s", source_id)
        return None

    url_canonical = _canonical_url(link)
    source_domain = _extract_domain(url_canonical or link)
    published_at = _parse_date(entry)
    content_text = summary  # RSS-only MVP: content_text == summary
    content_hash = _hash((title + summary).lower())

    return {
        "source_id": source_id,
        "source_domain": source_domain,
        "url_original": url_original or link,
        "url_canonical": url_canonical,
        "title": title,
        "summary": summary,
        "content_text": content_text,
        "published_at": published_at,
        "discovered_at": _now_iso(),
        "content_hash": content_hash,
        "rule_score": 0,
        "status": "new",
    }


def persist_normalized_item(item: dict, conn) -> int | None:
    """
    Insert a normalized item into the DB.
    Returns the new row id, or None if the canonical URL already exists.
    """
    cursor = conn.cursor()
    existing = cursor.execute(
        "SELECT id FROM normalized_items WHERE url_canonical = ?",
        (item["url_canonical"],),
    ).fetchone()
    if existing:
        return None

    cursor.execute(
        """
        INSERT INTO normalized_items
            (source_id, url_original, url_canonical, source_domain,
             title, summary, content_text, published_at, discovered_at,
             content_hash, rule_score, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item["source_id"],
            item["url_original"],
            item["url_canonical"],
            item["source_domain"],
            item["title"],
            item["summary"],
            item["content_text"],
            item["published_at"],
            item["discovered_at"],
            item["content_hash"],
            item["rule_score"],
            item["status"],
        ),
    )
    return cursor.lastrowid


def normalize_and_persist_all(conn) -> int:
    """
    Read all raw_items not yet normalised, normalize and insert them.
    Returns count of newly inserted normalized items.
    """
    cursor = conn.cursor()
    raw_rows = cursor.execute(
        """
        SELECT r.id, r.source_id, r.url_original, r.raw_payload
        FROM raw_items r
        WHERE NOT EXISTS (
            SELECT 1 FROM normalized_items n WHERE n.url_canonical = r.url_original
        )
        """
    ).fetchall()

    inserted = 0
    for row in raw_rows:
        item = normalize_raw_item(row["raw_payload"], row["source_id"], row["url_original"])
        if not item:
            continue
        row_id = persist_normalized_item(item, conn)
        if row_id:
            inserted += 1

    conn.commit()
    logger.info("Normalized %d new items", inserted)
    return inserted

