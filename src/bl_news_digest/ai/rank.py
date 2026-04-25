"""Ranking logic: select top-N items from reviewed set.

Scoring formula:
  composite = (relevance_score * 3 + business_impact_score * 2
               + actionability_score + urgency_score) / 7

Only 'include' decisions are eligible.
At most 2 items per source_domain to avoid overrepresentation.
"""

from __future__ import annotations

import logging
import sqlite3

from bl_news_digest.ai.schemas import ItemReview

log = logging.getLogger(__name__)

MAX_PER_DOMAIN = 2


def _composite_score(review: ItemReview) -> float:
    return (
        review.relevance_score * 3
        + review.business_impact_score * 2
        + review.actionability_score
        + review.urgency_score
    ) / 7.0


def select_top_n(
    reviews: list[tuple[int, ItemReview]],
    conn: sqlite3.Connection,
    top_n: int = 5,
) -> list[tuple[int, ItemReview]]:
    """Return the top-N ranked items from the reviewed set.

    - Excludes items with decision='exclude'.
    - Limits overrepresentation: at most MAX_PER_DOMAIN items per source domain.
    - Sorts by composite score descending.
    """
    # Fetch domain for each item_id
    id_to_domain: dict[int, str] = {}
    for item_id, _ in reviews:
        row = conn.execute(
            "SELECT source_domain FROM normalized_items WHERE id = ?", (item_id,)
        ).fetchone()
        id_to_domain[item_id] = row["source_domain"] if row else ""

    # Filter to 'include' decisions and sort
    candidates = [
        (item_id, review)
        for item_id, review in reviews
        if review.decision == "include"
    ]
    candidates.sort(key=lambda x: _composite_score(x[1]), reverse=True)

    # Apply per-domain cap
    selected: list[tuple[int, ItemReview]] = []
    selected_ids: set[int] = set()
    domain_counts: dict[str, int] = {}
    for item_id, review in candidates:
        domain = id_to_domain[item_id]
        if domain_counts.get(domain, 0) >= MAX_PER_DOMAIN:
            log.debug("Skipping item %d (%s): domain cap reached for %s", item_id, review.topic_type, domain)
            continue
        selected.append((item_id, review))
        selected_ids.add(item_id)
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        if len(selected) >= top_n:
            break

    # Mark selected items as 'selected' and all other reviewed items as 'reviewed'
    # so that deduplicate()'s cross-run pass and review_all_shortlisted() do not
    # re-process them in future pipeline runs.
    all_reviewed_ids = {item_id for item_id, _ in reviews}
    for item_id, _ in selected:
        conn.execute(
            "UPDATE normalized_items SET status = 'selected' WHERE id = ?", (item_id,)
        )
    for item_id in all_reviewed_ids - selected_ids:
        conn.execute(
            "UPDATE normalized_items SET status = 'reviewed' WHERE id = ?", (item_id,)
        )
    conn.commit()

    log.info("Ranked %d candidates -> selected %d top items", len(candidates), len(selected))
    return selected
