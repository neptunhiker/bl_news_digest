"""Keyword allowlist for AVGS / BeginnerLuft relevance filtering."""

# Any item whose title or summary contains at least one of these terms
# (case-insensitive) is forwarded to the AI reviewer.
# Items with zero matches are discarded without an AI call.

KEYWORDS: list[str] = [
    # Hard include — core AVGS terms
    "avgs",
    "aktivierungs- und vermittlungsgutschein",
    "§45 sgb iii",
    "maßnahme bei einem träger",
    "azav",
    # Provider / compliance
    "trägerzulassung",
    "maßnahmezulassung",
    "maßnahmenzulassung",
    "akkreditierung",
    "coaching und aktivierung",
    "bildungsträger",
]

# Domains that must always be rejected regardless of keyword matches.
BLOCKED_DOMAINS: list[str] = [
    "beginnerluft.de",
]
