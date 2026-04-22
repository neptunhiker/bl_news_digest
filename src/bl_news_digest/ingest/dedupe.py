"""Deduplication — marks near-duplicate normalized items as rejected."""

from __future__ import annotations

import logging

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Title similarity threshold (0–100). Items above this are considered near-duplicates.
_TITLE_SIMILARITY_THRESHOLD = 88

# How many days of digest history to check against when deduplicating.
_HISTORY_LOOKBACK_DAYS = 90


def deduplicate(conn) -> int:
    """
    Find near-duplicate normalized items (by title similarity) among 'new' items
    and mark the lower-priority duplicates as 'rejected'.

    Two passes are performed:
    1. Cross-run: reject any new item whose title is too similar to an item that
       was already selected (posted) in a previous digest within the last
       _HISTORY_LOOKBACK_DAYS days.
    2. Within-run: among the remaining new items, reject later duplicates of
       earlier items in the same batch.

    Exact URL and content-hash duplicates are already prevented at insert time
    in normalize.py. This pass handles near-duplicates with slightly different
    titles or URLs.

    Returns the number of items marked as rejected.
    """
    cursor = conn.cursor()

    # --- Pass 1: cross-run historical deduplication ---
    selected_rows = cursor.execute(
        """
        SELECT id, title
        FROM normalized_items
        WHERE status = 'selected'
          AND discovered_at >= datetime('now', ? || ' days')
        ORDER BY id
        """,
        (f"-{_HISTORY_LOOKBACK_DAYS}",),
    ).fetchall()
    selected_anchors = [(row["id"], row["title"] or "") for row in selected_rows]

    new_rows = cursor.execute(
        "SELECT id, title, source_id FROM normalized_items WHERE status = 'new' ORDER BY id"
    ).fetchall()
    items = [(row["id"], row["title"] or "", row["source_id"]) for row in new_rows]

    rejected_ids: set[int] = set()

    for new_id, new_title, _ in items:
        for _sel_id, sel_title in selected_anchors:
            score = fuzz.token_sort_ratio(new_title, sel_title)
            if score >= _TITLE_SIMILARITY_THRESHOLD:
                rejected_ids.add(new_id)
                logger.debug(
                    "Cross-run near-duplicate (score=%d): new [%d] %r ~ selected [%d] %r",
                    score, new_id, new_title, _sel_id, sel_title,
                )
                break  # no need to compare against further anchors

    # --- Pass 2: within-run deduplication ---
    for i, (id_a, title_a, _) in enumerate(items):
        if id_a in rejected_ids:
            continue
        for id_b, title_b, _ in items[i + 1:]:
            if id_b in rejected_ids:
                continue
            score = fuzz.token_sort_ratio(title_a, title_b)
            if score >= _TITLE_SIMILARITY_THRESHOLD:
                # Keep the earlier (lower id) item; reject the later one
                rejected_ids.add(id_b)
                logger.debug(
                    "Within-run near-duplicate (score=%d): [%d] %r ~ [%d] %r",
                    score, id_a, title_a, id_b, title_b,
                )

    if rejected_ids:
        cursor.executemany(
            "UPDATE normalized_items SET status = 'rejected' WHERE id = ?",
            [(rid,) for rid in rejected_ids],
        )
        conn.commit()
        logger.info("Deduplication: rejected %d near-duplicate items", len(rejected_ids))

    return len(rejected_ids)

