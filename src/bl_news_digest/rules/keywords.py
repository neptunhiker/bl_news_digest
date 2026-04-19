"""Keyword allowlist for AVGS / BeginnerLuft relevance filtering."""

# Any item whose title or summary contains at least one of these terms
# (case-insensitive) is forwarded to the AI reviewer.
# Items with zero matches are discarded without an AI call.

KEYWORDS: list[str] = [
    # Hard include — core AVGS terms
    "avgs",
    "aktivierungs- und vermittlungsgutschein",
    "aktivierungsgutschein",
    "vermittlungsgutschein",
    "§45 sgb iii",
    "paragraph 45",
    "maßnahme bei einem träger",
    "azav",
    # Provider / compliance
    "trägerzulassung",
    "maßnahmezulassung",
    "fachkundige stelle",
    "akkreditierung",
    "coaching und aktivierung",
    "bildungsträger",
    "zulassung",
    # Labor market / demand
    "jobcenter",
    "agentur für arbeit",
    "bundesagentur für arbeit",
    "arbeitslos",
    "arbeitssuchend",
    "sgb ii",
    "sgb iii",
    "berufliche neuorientierung",
    "arbeitsmarkt",
    "beschäftigung",
    "erwerbslosigkeit",
    # BeginnerLuft-fit context
    "burnout",
    "migration",
    "wiedereinstieg",
    "gründung",
    "existenzgründung",
    "karrierecoaching",
    "berufsberatung",
    "qualifizierung",
]
