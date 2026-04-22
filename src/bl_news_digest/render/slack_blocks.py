"""Slack Block Kit renderer for the daily AVGS digest."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

# A "digest item" dict combining NormalizedItem + ItemReview fields for rendering.
# Keys: title, url_canonical, source_domain, summary, why_relevant,
#       recommended_actions (list[str]), relevance_score, rank
DigestItemDict = dict[str, Any]


def _header_block(digest_date: date) -> dict:
    formatted = digest_date.strftime("%-d. %B %Y")
    return {
        "type": "header",
        "text": {"type": "plain_text", "text": f"BeginnerLuft AVGS-News — {formatted}", "emoji": True},
    }


def _stats_context_block(scanned: int, selected: int) -> dict:
    return {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": (
                    f"*{scanned}* Artikel gescannt  ·  "
                    f"*{selected}* ausgewählt"
                ),
            }
        ],
    }


def _divider() -> dict:
    return {"type": "divider"}


def _item_blocks(item: DigestItemDict, rank: int) -> list[dict]:
    title = item.get("title", "(kein Titel)")
    url = item.get("url_canonical", "")
    domain = item.get("source_domain", "")
    summary = item.get("summary") or ""
    why_relevant = item.get("why_relevant") or ""
    actions: list[str] = item.get("recommended_actions") or []
    action_text = actions[0] if actions else ""

    title_link = f"<{url}|{title}>" if url else title

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{rank}. {title_link}*",
            },
        },
    ]

    if summary:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary},
        })

    detail_lines: list[str] = []
    if why_relevant:
        detail_lines.append(f":mag: *Warum relevant für BeginnerLuft:* {why_relevant}")
    if action_text:
        detail_lines.append(f":dart: *Empfehlung:* {action_text}")

    if detail_lines:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(detail_lines)},
        })

    source_link = f"<{url}|{domain}>" if url else domain
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"Quelle: {source_link}"}],
    })

    return blocks





def render_blocks(
    items: list[DigestItemDict],
    *,
    digest_date: date | None = None,
    scanned: int = 0,
) -> list[dict]:
    """Build and return a Slack Block Kit blocks list for the digest."""
    today = digest_date or date.today()
    blocks: list[dict] = [
        _header_block(today),
        _stats_context_block(scanned, len(items)),
        _divider(),
    ]

    for rank, item in enumerate(items, start=1):
        blocks.extend(_item_blocks(item, rank))
        blocks.append(_divider())

    return blocks


def render_fallback_text(items: list[DigestItemDict], digest_date: date | None = None) -> str:
    """Plain-text fallback for notifications and accessibility."""
    today = digest_date or date.today()
    lines = [f"AVGS-Digest — {today.strftime('%-d. %B %Y')}"]
    for rank, item in enumerate(items, start=1):
        lines.append(f"\n{rank}. {item.get('title', '')}")
        lines.append(item.get("url_canonical", ""))
    return "\n".join(lines)


def blocks_to_json(blocks: list[dict]) -> str:
    """Serialise blocks to a JSON string (for logging / DB storage)."""
    return json.dumps(blocks, ensure_ascii=False, indent=2)

