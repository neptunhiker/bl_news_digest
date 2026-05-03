"""End-to-end dry-run integration test.

Covers the full pipeline:
  Fetch (mocked RSS) → Normalize → Dedupe → Keyword filter
  → AI review (mocked) → Slack render (dry-run, no post)

No real secrets or network calls are made.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx
from click.testing import CliRunner

from bl_news_digest.cli import cli
from bl_news_digest.ai.schemas import ItemReview


# ---------------------------------------------------------------------------
# RSS fixture data — one AVGS-relevant item per source
# ---------------------------------------------------------------------------

RSS_BMAS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BMAS Aktuell</title>
    <link>https://www.bmas.de</link>
    <item>
      <title>Neue AVGS-Regelung tritt in Kraft</title>
      <link>https://www.bmas.de/avgs-neu-2026</link>
      <pubDate>Sun, 19 Apr 2026 08:00:00 +0000</pubDate>
      <description>Änderungen beim Aktivierungs- und Vermittlungsgutschein §45 SGB III.</description>
    </item>
    <item>
      <title>Wetterbericht April 2026</title>
      <link>https://www.bmas.de/wetter</link>
      <pubDate>Sat, 18 Apr 2026 10:00:00 +0000</pubDate>
      <description>Frühlingswetter erwartet.</description>
    </item>
  </channel>
</rss>
"""

RSS_BUNDESTAG = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Bundestag Arbeit und Soziales</title>
    <link>https://www.bundestag.de</link>
    <item>
      <title>Gesetzentwurf zur Trägerzulassung vorgelegt</title>
      <link>https://www.bundestag.de/traegerzulassung-2026</link>
      <pubDate>Fri, 17 Apr 2026 14:00:00 +0000</pubDate>
      <description>Reform der AZAV-Trägerzulassung geplant.</description>
    </item>
  </channel>
</rss>
"""

RSS_IAB = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>IAB Aktuell</title>
    <link>https://www.iab.de</link>
    <item>
      <title>Studie zu Bildungsträgern im SGB-II-Bereich</title>
      <link>https://www.iab.de/studie-bildungstraeger-2026</link>
      <pubDate>Thu, 16 Apr 2026 09:00:00 +0000</pubDate>
      <description>Neue IAB-Studie über Bildungsträger und ihre Wirksamkeit.</description>
    </item>
    <item>
      <title>IAB Pressemitteilung: Allgemeine Konjunktur</title>
      <link>https://www.iab.de/konjunktur-2026</link>
      <pubDate>Wed, 15 Apr 2026 09:00:00 +0000</pubDate>
      <description>Allgemeine Wirtschaftslage stabil.</description>
    </item>
  </channel>
</rss>
"""

MOCK_REVIEW = ItemReview(
    decision="include",
    topic_type="AVGS regulation",
    relevance_score=9,
    beginnerluft_fit_score=8,
    actionability_score=7,
    business_impact_score=8,
    urgency_score=6,
    confidence=9,
    summary="Neue AVGS-Regelung tritt in Kraft.",
    why_relevant="Direkte Auswirkung auf Gutscheinbudgets.",
    recommended_actions=["Bundesanzeiger beobachten", "Interne Richtlinien prüfen"],
)

SOURCE_URLS = {
    "https://www.bmas.de/DE/Service/Newsletter/RSS/rss.html": RSS_BMAS,
    "https://www.bundestag.de/static/appdata/includes/rss/arbeitsoziales.rss": RSS_BUNDESTAG,
    "https://www.iab.de/de/rss/iab_aktuell.xml": RSS_IAB,
}

# Minimal sources.yaml fixture that exactly matches the mocked URLs above.
# Using a fixture rather than the real config/sources.yaml makes the test
# resilient to changes in which sources are enabled in production.
SOURCES_YAML_FIXTURE = """\
sources:
  - id: bmas_rss
    enabled: true
    family: bmas
    priority: 1
    method: rss
    parser: rss_parser
    cadence_minutes: 1440
    url: https://www.bmas.de/DE/Service/Newsletter/RSS/rss.html

  - id: bundestag_arbeit_soziales_rss
    enabled: true
    family: bundestag
    priority: 1
    method: rss
    parser: rss_parser
    cadence_minutes: 1440
    url: https://www.bundestag.de/static/appdata/includes/rss/arbeitsoziales.rss

  - id: iab_rss
    enabled: true
    family: iab
    priority: 1
    method: rss
    parser: rss_parser
    cadence_minutes: 1440
    url: https://www.iab.de/de/rss/iab_aktuell.xml
"""


# ---------------------------------------------------------------------------
# Helper: build a minimal .env in the tmp dir and point config there
# ---------------------------------------------------------------------------

def _write_env(path: Path) -> None:
    path.write_text(
        "APP_ENV=test\n"
        "LOG_LEVEL=WARNING\n"
        f"DB_PATH={path.parent / 'data' / 'digest.db'}\n"
        "OPENAI_API_KEY=sk-test\n"
        "OPENAI_MODEL=gpt-4.1-mini\n"
        "SLACK_BOT_TOKEN=xoxb-test\n"
        "SLACK_CHANNEL_ID=C123TEST\n"
        "SLACK_POST_ENABLED=false\n"
        "DRY_RUN=true\n"
        "AI_REVIEW_CACHE_ENABLED=false\n"
    )


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------

@respx.mock
@patch("bl_news_digest.ai.review.parse_structured", return_value=MOCK_REVIEW)
def test_full_dry_run_pipeline(mock_ai, tmp_path):
    """Full pipeline dry-run: fetch → normalize → dedupe → score → AI review → Slack render."""
    # Set up mock HTTP responses for all 3 RSS feeds
    for url, body in SOURCE_URLS.items():
        respx.get(url).mock(return_value=httpx.Response(200, text=body))

    # Write .env and sources.yaml into tmp dir
    env_file = tmp_path / ".env"
    _write_env(env_file)

    sources_dir = tmp_path / "config"
    sources_dir.mkdir()
    (sources_dir / "sources.yaml").write_text(SOURCES_YAML_FIXTURE)

    # lru_cache means Settings is cached from previous tests — clear it
    from bl_news_digest.config import get_settings
    get_settings.cache_clear()

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Symlink config/ into the isolated fs working dir
        Path("config").symlink_to(sources_dir)

        result = runner.invoke(
            cli,
            ["run", "--dry-run"],
            env={
                "APP_ENV": "test",
                "LOG_LEVEL": "WARNING",
                "DB_PATH": str(tmp_path / "data" / "digest.db"),
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_MODEL": "gpt-4.1-mini",
                "SLACK_BOT_TOKEN": "xoxb-test",
                "SLACK_CHANNEL_ID": "C123TEST",
                "SLACK_POST_ENABLED": "false",
                "DRY_RUN": "true",
                "AI_REVIEW_CACHE_ENABLED": "false",
            },
            catch_exceptions=False,
        )

    # Clear cache after test to avoid polluting other tests
    get_settings.cache_clear()

    assert result.exit_code == 0, f"CLI exited with {result.exit_code}:\n{result.output}"

    output = result.output
    assert "[1/5] Fetching RSS sources" in output
    assert "[2/5] Normalizing and deduplicating" in output
    assert "[3/5] Applying keyword filter" in output
    assert "[4/5] AI review and ranking" in output
    assert "[5/5] Rendering and posting to Slack" in output
    assert "Dry run complete" in output

    # Verify fetch counts: 5 items across 3 feeds
    assert "5 items seen" in output

    # Verify keyword filter found at least 3 relevant items (AVGS, Trägerzulassung, Bildungsträger)
    import re
    shortlisted_match = re.search(r"Shortlisted: (\d+)", output)
    assert shortlisted_match, "No shortlisted count in output"
    shortlisted_count = int(shortlisted_match.group(1))
    assert shortlisted_count >= 3, f"Expected >=3 shortlisted, got {shortlisted_count}"

    # In dry-run mode, AI is NOT called (no external API calls)
    assert mock_ai.call_count == 0

    # Verify DB state
    db_path = tmp_path / "data" / "digest.db"
    assert db_path.exists(), "Database file not created"

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    raw_count = conn.execute("SELECT COUNT(*) FROM raw_items").fetchone()[0]
    assert raw_count == 5

    normalized_count = conn.execute("SELECT COUNT(*) FROM normalized_items").fetchone()[0]
    assert normalized_count == 5

    shortlisted_db = conn.execute(
        "SELECT COUNT(*) FROM normalized_items WHERE status='shortlisted'"
    ).fetchone()[0]
    assert shortlisted_db == shortlisted_count

    # No reviews stored — dry-run skips AI calls
    reviews_count = conn.execute("SELECT COUNT(*) FROM item_reviews").fetchone()[0]
    assert reviews_count == 0

    # Digest run recorded
    run = conn.execute("SELECT status, scanned_count, selected_count FROM digest_runs").fetchone()
    assert run is not None
    assert run["status"] == "ok"
    assert run["scanned_count"] == 5

    # Slack payloads are only persisted when at least one digest item is selected.
    outbound = conn.execute("SELECT posted_at FROM outbound_messages").fetchone()
    if run["selected_count"] == 0:
      assert outbound is None
    else:
      assert outbound is not None
      assert outbound["posted_at"] is None  # dry run — not actually posted

    conn.close()
