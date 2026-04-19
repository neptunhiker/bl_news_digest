"""Keyword-presence filter for AVGS / BeginnerLuft relevance.

Logic:
1. If the item's domain is in BLOCKED_DOMAINS  -> reject immediately (score=0, status='rejected')
2. If title or summary contains any KEYWORD    -> pass to AI (score=1, status='shortlisted')
3. Otherwise                                   -> discard silently (score=0, status='rejected')
"""

from __future__ import annotations

import sqlite3
import logging

from bl_news_digest.rules.keywords import BLOCKED_DOMAINS, KEYWORDS

log = logging.getLogger(__name__)


def _matches_any_keyword(text: str) -> bool:
    """Return True if *text* contains at least one keyword (case-insensitive)."""
    lower = text.lower()
    return any(kw in lower for kw in KEYWORDS)


def score_item(title: str, summary: str, source_domain: str) -> tuple[int, str]:
    """Score a single normalized item.

    Returns (rule_score, status) where:
      - rule_score=0, status='rejected'   -> blocked domain or no keyword match
      - rule_score=1, status='shortlisted' -> at least one keyword matched
    """
    domain_lower = source_domain.lower()
    if any(blocked in domain_lower for blocked in BLOCKED_DOMAINS):
        return 0, "rejected"

    combined = f"{title} {summary}"
    if _matches_any_keyword(combined):
        return 1, "shortlisted"

    return 0, "rejected"


def apply_scores(conn: sqlite3.Connection) -> tuple[int, int]:
    """Score all normalized items with status='new' and update the DB.

    Returns (shortlisted_count, rejected_count).
    """
    rows = conn.execute(
        """
        SELECT id, title, summary, source_domain
        FROM normalized_items
        WHERE status = 'new'
        """
    ).fetchall()

    shortlisted = 0
    rejected = 0

    for row in rows:
        score, status = score_item(
            row["title"] or "",
            row["summary"] or "",
            row["source_domain"] or "",
        )
        conn.execute(
            "UPDATE normalized_items SET rule_score = ?, status = ? WHERE id = ?",
            (score, status, row["id"]),
        )
        if status == "shortlisted":
            shortlisted += 1
        else:
            rejected += 1
            log.debug("Rejected (no keyword match): %s", row["title"])

    conn.commit()
    log.info("Scorer: %d shortlisted, %d rejected", shortlisted, rejected)
    return shortlisted, rejected
