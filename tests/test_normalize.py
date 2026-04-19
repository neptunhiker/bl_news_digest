"""Tests for the normalizer."""

from __future__ import annotations

from bl_news_digest.ingest.normalize import (
    _canonical_url,
    _extract_domain,
    normalize_raw_item,
)


def test_canonical_url_strips_tracking_params():
    url = "https://www.bmas.de/article?utm_source=newsletter&utm_campaign=avgs&id=42"
    result = _canonical_url(url)
    assert "utm_source" not in result
    assert "utm_campaign" not in result
    assert "id=42" in result


def test_canonical_url_lowercases_host():
    url = "https://WWW.BMAS.DE/article"
    result = _canonical_url(url)
    assert result.startswith("https://www.bmas.de/")


def test_extract_domain_strips_www():
    assert _extract_domain("https://www.bmas.de/article") == "bmas.de"


def test_normalize_raw_item_basic():
    raw = str({
        "title": "Neue AVGS-Änderungen 2026",
        "link": "https://www.bmas.de/avgs-2026",
        "summary": "Wichtige Änderungen bei AVGS und Trägerzulassung.",
        "published_parsed": (2026, 4, 19, 8, 0, 0, 0, 0, 0),
        "updated_parsed": None,
        "id": "https://www.bmas.de/avgs-2026",
    })

    item = normalize_raw_item(raw, "bmas_rss", "https://www.bmas.de/avgs-2026")

    assert item is not None
    assert item["title"] == "Neue AVGS-Änderungen 2026"
    assert item["source_id"] == "bmas_rss"
    assert item["source_domain"] == "bmas.de"
    assert item["url_canonical"] == "https://www.bmas.de/avgs-2026"
    assert item["status"] == "new"
    assert item["content_hash"]


def test_normalize_raw_item_strips_html_from_summary():
    raw = str({
        "title": "Test Artikel",
        "link": "https://www.bmas.de/test",
        "summary": "<p>Wichtig: <strong>AVGS</strong> Änderung</p>",
        "published_parsed": None,
        "updated_parsed": None,
        "id": "https://www.bmas.de/test",
    })

    item = normalize_raw_item(raw, "bmas_rss", "https://www.bmas.de/test")
    assert item is not None
    assert "<p>" not in item["summary"]
    assert "<strong>" not in item["summary"]
    assert "AVGS" in item["summary"]


def test_normalize_raw_item_returns_none_for_empty_entry():
    raw = str({"title": "", "link": "", "summary": ""})
    item = normalize_raw_item(raw, "bmas_rss", "")
    assert item is None
