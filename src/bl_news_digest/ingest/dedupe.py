"""Deduplication — marks near-duplicate normalized items as rejected."""

from __future__ import annotations

import logging

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Title similarity threshold (0–100). Items above this are considered near-duplicates.
_TITLE_SIMILARITY_THRESHOLD = 88


def deduplicate(conn) -> int:
    """
    Find near-duplicate normalized items (by title similarity) among 'new' items
    and mark the lower-priority duplicates as 'rejected'.

    Exact URL and content-hash duplicates are already prevented at insert time
    in normalize.py. This pass handles near-duplicates with slightly different titles.

    Returns the number of items marked as rejected.
    """
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT id, title, source_id FROM normalized_items WHERE status = 'new' ORDER BY id"
    ).fetchall()

    items = [(row["id"], row["title"] or "", row["source_id"]) for row in rows]
    rejected_ids: set[int] = set()

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
                    "Near-duplicate (score=%d): [%d] %r ~ [%d] %r",
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

