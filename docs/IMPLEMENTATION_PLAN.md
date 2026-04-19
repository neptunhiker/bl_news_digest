# NEWS_DIGEST.md

## BeginnerLuft AVGS External News Digest - Local-First MVP Implementation Plan

This document is written for an AI engineer that will implement the system step by step.

The goal is to build a production-ready Python pipeline that:
- ingests selected external official public sources relevant to AVGS, AZAV, SGB II / SGB III, and labor-market policy
- normalizes and deduplicates all source items
- filters items for AVGS and BeginnerLuft relevance
- uses AI only for structured review and ranking of shortlisted items
- selects the top 5 most relevant items
- posts a formatted daily digest into a specific Slack `#news` channel
- runs automatically via cron on a Hetzner server
- is observable, testable, and cheap enough to run daily

IMPORTANT:
- This system is for **external intelligence only**.
- Do **not** include BeginnerLuft website content, blog posts, social posts, or any other BeginnerLuft-owned content.
- Any source originating from BeginnerLuft must be rejected immediately.
- The recommended workflow is **local development -> GitHub -> clone on Hetzner -> cron execution on Hetzner**.
- This is **not** a web app. It does **not** need a subdomain, nginx, or a public endpoint.

---

## 0. High-level requirements

### Functional requirements
- [ ] Fetch data daily from a fixed allowlist of MVP sources
- [ ] Support source types: RSS and HTML in MVP
- [ ] Persist raw and normalized data in SQLite
- [ ] Deduplicate exact and near-duplicate items
- [ ] Score items with rule-based AVGS / BeginnerLuft relevance logic
- [ ] Send only shortlisted items to an AI reviewer
- [ ] Rank the reviewed items and select the top 5
- [ ] Render a Slack digest using Block Kit
- [ ] Post the digest to a configured Slack channel
- [ ] Save run history and posted message metadata

### Non-functional requirements
- [ ] Must run unattended on a Hetzner server
- [ ] Must be idempotent for repeated daily runs
- [ ] Must be robust against partial failures
- [ ] Must minimize AI cost through rule filtering and caching
- [ ] Must be easy to extend with new sources later
- [ ] Must be auditable: every decision should be inspectable
- [ ] Must be implemented as a local Python service plus cron, not as a web app

### MVP principles
- [ ] Implement only 3 sources in Phase 1
- [ ] Do not implement any appendix source in MVP
- [ ] Prefer stability over completeness
- [ ] Prefer official sources over media commentary
- [ ] Prefer deterministic filtering before AI

---

## 1. Recommended working model

### 1.1 Development and deployment model

Use this workflow:

- [ ] Develop locally on your own machine
- [ ] Version everything in Git
- [ ] Push to GitHub
- [ ] Clone the repo once on Hetzner
- [ ] Pull updates on Hetzner whenever changes are deployed
- [ ] Run the script daily on Hetzner via cron

### 1.2 Why this model is preferred

- [ ] Keeps local experimentation separate from production
- [ ] Makes rollback easy
- [ ] Keeps GitHub as the source of truth
- [ ] Avoids editing production code directly on the server
- [ ] Makes future collaboration easier

### 1.3 How the runtime actually works on Hetzner

The runtime model is simple:

- one folder on Hetzner, for example `~/apps/bl_news_digest`
- one Python virtual environment in that folder
- one `.env` file in that folder
- one SQLite database in `data/`
- one cron job that runs a Python CLI command once per day

Example command:

```bash
cd ~/apps/bl_news_digest && . .venv/bin/activate && python -m bl_news_digest.cli run
```

That command:
- loads configuration from `.env`
- fetches source data
- filters and ranks items
- posts the digest to Slack
- stores logs and database updates
- exits

### 1.4 Explicit infrastructure clarification

- [ ] No subdomain required
- [ ] No Django integration required
- [ ] No web server required
- [ ] No background queue required for MVP
- [ ] No Docker required for MVP

---

## 2. Scope definition

### 2.1 In-scope source families for MVP

Implement **only** the following 3 RSS sources in MVP. All sources use the same RSS parser. No HTML scraping in MVP.

#### Source 1 - BMAS (Bundesministerium für Arbeit und Soziales)
- [ ] BMAS RSS feed

Endpoint:
- `https://www.bmas.de/DE/Service/Newsletter/RSS/rss.html`

Why included:
- Ministry-level labor and social policy updates
- Legal and political signals directly relevant to AVGS providers
- Higher-level changes affecting labor-market activation context

#### Source 2 - Bundestag Arbeit und Soziales
- [ ] Bundestag Arbeit und Soziales RSS feed

Endpoint:
- `https://www.bundestag.de/static/appdata/includes/rss/arbeitsoziales.rss`

Why included:
- Early legislative and committee signals
- Forward-looking changes that may affect AVGS, Jobcenter practice, or labor-market instruments

#### Source 3 - IAB (Institut für Arbeitsmarkt- und Berufsforschung)
- [ ] IAB current research and news RSS feed

Endpoint:
- `https://www.iab.de/de/rss/iab_aktuell.xml` *(verify this URL before first run)*

Why included:
- Independent labor market research directly relevant to AVGS, coaching, and activation programs
- Evidence-based insights on employment trends, Jobcenter behavior, and coaching effectiveness
- Research signals that often precede policy changes affecting AVGS providers

### 2.2 Explicit exclusions

Do not implement these in MVP.

- [ ] BeginnerLuft website
- [ ] BeginnerLuft blog
- [ ] BeginnerLuft LinkedIn
- [ ] BeginnerLuft Instagram
- [ ] BeginnerLuft YouTube
- [ ] Newspaper scraping
- [ ] Arbitrary web search
- [ ] Social media scraping
- [ ] Email delivery
- [ ] Full UI dashboard
- [ ] PostgreSQL migration
- [ ] Human approval workflow
- [ ] Appendix sources

### 2.3 Hard exclusion rule

The following rule must be implemented globally:

```python
if "beginnerluft" in source_domain.lower():
    reject_immediately = True
```

Acceptance criteria:
- [ ] MVP uses only the 3 approved source groups
- [ ] No BeginnerLuft-owned source is present in the source registry
- [ ] Every source in MVP has an explicit adapter or parser strategy

---

## 3. Bootstrap from scratch - local machine first

This section is the exact recommended sequence for creating the project from zero.

### 3.1 Create the project locally

Choose a local project folder, for example:

```bash
mkdir -p ~/apps/bl_news_digest
cd ~/apps/bl_news_digest
```

Tasks:
- [x] Create local project folder
- [x] Open it in your editor
- [x] Use a dedicated Python version if needed

### 3.2 Initialize Git locally

```bash
git init
```

Tasks:
- [x] Initialize local Git repository
- [x] Confirm `git status` works

### 3.3 Create the initial folder structure

```bash
mkdir -p src/bl_news_digest
mkdir -p tests
mkdir -p config
mkdir -p data/raw
mkdir -p data/snapshots
mkdir -p logs
```

Tasks:
- [x] Create source package folder
- [x] Create tests folder
- [x] Create config folder
- [x] Create data folders
- [x] Create logs folder

### 3.4 Create the virtual environment locally

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Tasks:
- [x] Create `.venv`
- [x] Activate it
- [x] Confirm `python --version`
- [x] Confirm `which python`

### 3.5 Create `.gitignore`

Create `.gitignore` with the following content:

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
*.so
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Virtual environment
.venv/
venv/

# Environment and secrets
.env
.env.*
!.env.example

# Logs and runtime data
logs/
*.log

# Local data
/data/*.db
/data/*.sqlite
/data/*.sqlite3
/data/raw/
/data/snapshots/

# OS / editor files
.DS_Store
.idea/
.vscode/
```

Tasks:
- [x] Create `.gitignore`
- [x] Ensure `.env` is ignored
- [x] Ensure database files are ignored
- [x] Ensure logs are ignored
- [x] Keep `.env.example` committed

### 3.6 Create `.env.example`

Create `.env.example` with placeholder values only:

```env
APP_ENV=development
TIMEZONE=Europe/Berlin
LOG_LEVEL=INFO
HTTP_USER_AGENT=BeginnerLuft-AVGS-NewsBot/0.1

DB_PATH=./data/app.db

OPENAI_API_KEY=sk-example-replace-me-later
OPENAI_MODEL=gpt-4.1-mini

SLACK_BOT_TOKEN=xoxb-example-replace-me-later
SLACK_CHANNEL_ID=C0123456789
SLACK_POST_ENABLED=false

DIGEST_TOP_N=5
DRY_RUN=true
AI_REVIEW_CACHE_ENABLED=true
```

Tasks:
- [x] Create `.env.example`
- [x] Use fake placeholder secrets only
- [x] Do not place real credentials into Git

### 3.7 Create local `.env`

Create `.env` by copying the example:

```bash
cp .env.example .env
```

Tasks:
- [x] Create `.env` locally
- [x] Keep fake tokens at first if implementation is still in progress
- [ ] Replace later with real values only when ready

### 3.8 Create `README.md`

The README should contain:
- project goal
- local setup instructions
- how to run a dry run
- how to run tests
- how deployment to Hetzner works

Tasks:
- [x] Create `README.md`
- [x] Document local setup
- [x] Document production setup

### 3.9 Create initial commit locally

```bash
git add .
git commit -m "Initial project skeleton for AVGS Slack digest"
```

Tasks:
- [x] Create initial commit
- [x] Confirm `.env` is not tracked

---

## 4. Create the GitHub repo and connect it

### 4.1 Create an empty GitHub repository

Create a new GitHub repo manually.

Recommendations:
- [ ] Make it public (no secrets in code; `.env` is gitignored)
- [ ] Do not auto-add README
- [ ] Do not auto-add `.gitignore`
- [ ] Do not auto-add license unless desired

### 4.2 Connect local repo to GitHub

Example:

```bash
git remote add origin git@github.com:YOURNAME/bl_news_digest.git
git branch -M main
git push -u origin main
```

Tasks:
- [ ] Add remote
- [ ] Rename branch to `main`
- [ ] Push initial commit

### 4.3 Ongoing developer workflow

Use this flow:

```bash
git add .
git commit -m "Implement source registry"
git push
```

Tasks:
- [ ] Commit frequently
- [ ] Keep production deployment separate from coding

---

## 5. Delivery phases

This implementation must be executed in phases. Do not skip ahead until the acceptance criteria of the current phase are met.

---

# Phase 1 - Repository, environment, and project skeleton

## Objectives
Create the Python project structure, environment management, configuration loading, and local run entrypoints.

## Tasks
- [x] Create `pyproject.toml`
- [x] Add dependency management
- [x] Create package structure under `src/bl_news_digest/`
- [x] Create CLI entrypoint `python -m bl_news_digest.cli`
- [x] Add configuration loader using environment variables
- [x] Add structured logging configuration
- [x] Add `README.md` with setup and run instructions

## Required folder structure
```text
bl_news_digest/
├─ pyproject.toml
├─ .gitignore
├─ .env.example
├─ README.md
├─ config/
│  └─ sources.yaml
├─ data/
│  ├─ raw/
│  ├─ snapshots/
│  └─ app.db
├─ logs/
├─ src/
│  └─ bl_news_digest/
│     ├─ __init__.py
│     ├─ cli.py
│     ├─ config.py
│     ├─ db.py
│     ├─ models.py
│     ├─ sources/
│     │  ├─ __init__.py
│     │  ├─ base.py
│     │  ├─ bmas.py
│     │  ├─ bundestag.py
│     │  └─ iab.py
│     ├─ ingest/
│     │  ├─ __init__.py
│     │  ├─ fetch.py
│     │  ├─ normalize.py
│     │  ├─ extract.py
│     │  └─ dedupe.py
│     ├─ rules/
│     │  ├─ __init__.py
│     │  ├─ keywords.py
│     │  ├─ scorer.py
│     │  └─ taxonomy.py
│     ├─ ai/
│     │  ├─ __init__.py
│     │  ├─ client.py
│     │  ├─ prompts.py
│     │  ├─ schemas.py
│     │  ├─ review.py
│     │  └─ rank.py
│     ├─ render/
│     │  ├─ __init__.py
│     │  ├─ slack_blocks.py
│     │  └─ slack_client.py
│     └─ ops/
│        ├─ __init__.py
│        ├─ logging_conf.py
│        ├─ monitoring.py
│        ├─ health.py
│        └─ alerts.py
└─ tests/
```

## Suggested dependencies
- [ ] `requests` *(skipped — RSS-only, httpx used instead)*
- [x] `httpx`
- [x] `feedparser`
- [ ] `beautifulsoup4` *(skipped — RSS-only MVP)*
- [ ] `lxml` *(skipped — RSS-only MVP)*
- [ ] `trafilatura` *(skipped — RSS-only MVP)*
- [x] `pydantic`
- [x] `python-dotenv`
- [x] `rapidfuzz`
- [x] `slack_sdk`
- [x] `tenacity`
- [x] `orjson`
- [x] `pytest`
- [x] `freezegun`
- [x] `responses` or `respx`

## Deliverables
- [x] A runnable Python package
- [x] A CLI command that prints config and exits successfully
- [x] Logging to stdout and file

## Acceptance criteria
- [x] `python -m bl_news_digest.cli doctor` runs successfully
- [x] Missing required env vars produce clear errors
- [x] Logs are emitted in structured text or JSON format

---

# Phase 2 - Configuration, secrets, source registry, and local commands

## Objectives
Create a stable configuration model for the app and a formal source registry.

## Tasks
- [x] Define required env vars
- [x] Implement config validation with Pydantic
- [x] Create a source registry file in `config/sources.yaml`
- [x] Assign each source an ID, family, priority, fetch method, cadence, and parser name
- [x] Add source toggles so sources can be enabled or disabled without code changes
- [x] Add hard exclusion domains list, including BeginnerLuft
- [x] Add a local `doctor` command
- [x] Add a local `run --dry-run` command
- [x] Add a local `list-sources` command

## Required environment variables
- [x] `OPENAI_API_KEY`
- [x] `OPENAI_MODEL`
- [x] `SLACK_BOT_TOKEN`
- [x] `SLACK_CHANNEL_ID`
- [x] `SLACK_POST_ENABLED`
- [x] `DB_PATH`
- [x] `LOG_LEVEL`
- [x] `HTTP_USER_AGENT`
- [x] `TIMEZONE`
- [x] `DIGEST_TOP_N`
- [x] `DRY_RUN`
- [x] `AI_REVIEW_CACHE_ENABLED`

## Example `sources.yaml`

```yaml
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
    url: https://www.iab.de/de/rss/iab_aktuell.xml  # verify before first run

hard_exclusion_domains:
  - beginnerluft.de
  - www.beginnerluft.de
  - linkedin.com
  - instagram.com
  - youtube.com
```

## Deliverables
- [x] A validated app config object
- [x] Source registry loads successfully
- [x] `doctor` command confirms config correctness

## Acceptance criteria
- [x] App fails fast on invalid env values
- [x] Source registry lists exactly the approved MVP sources
- [x] Exclusion domains are loaded and applied globally

---

# Phase 3 - Database schema and persistence

## Objectives
Create SQLite persistence for all pipeline stages.

## Tasks
- [x] Implement database initialization script
- [x] Create tables for sources, raw items, normalized items, reviews, digest runs, and outbound messages
- [x] Add indexes for canonical URL, hashes, and run dates
- [ ] Add helper methods for insert, upsert, and lookups
- [ ] Add migration approach for future schema changes

## Required SQLite tables

### `sources`
- [x] `id`
- [x] `family`
- [x] `priority`
- [x] `method`
- [x] `url`
- [x] `enabled`
- [x] `cadence_minutes`
- [x] `parser`

### `fetch_runs`
- [x] `id`
- [x] `source_id`
- [x] `started_at`
- [x] `finished_at`
- [x] `status`
- [x] `items_seen`
- [x] `items_new`
- [x] `error_text`

### `raw_items`
- [x] `id`
- [x] `source_id`
- [x] `fetch_run_id`
- [x] `url_original`
- [x] `external_id`
- [x] `raw_payload`
- [x] `raw_hash`
- [x] `stored_at`

### `normalized_items`
- [x] `id`
- [x] `source_id`
- [x] `url_original`
- [x] `url_canonical`
- [x] `source_domain`
- [x] `title`
- [x] `summary`
- [x] `content_text`
- [x] `published_at`
- [x] `discovered_at`
- [x] `content_hash`
- [x] `rule_score`
- [x] `status`

### `item_reviews`
- [x] `id`
- [x] `item_id`
- [x] `model_name`
- [x] `decision`
- [x] `topic_type`
- [x] `relevance_score`
- [x] `beginnerluft_fit_score`
- [x] `actionability_score`
- [x] `business_impact_score`
- [x] `urgency_score`
- [x] `confidence`
- [x] `summary`
- [x] `why_relevant_json`
- [x] `recommended_actions_json`
- [x] `review_json`
- [x] `created_at`

### `digest_runs`
- [x] `id`
- [x] `digest_date`
- [x] `started_at`
- [x] `finished_at`
- [x] `status`
- [x] `scanned_count`
- [x] `candidate_count`
- [x] `reviewed_count`
- [x] `selected_count`
- [x] `editor_note`

### `digest_items`
- [x] `digest_run_id`
- [x] `item_id`
- [x] `rank`
- [x] `final_score`
- [x] `why_relevant`
- [x] `recommended_action`

### `outbound_messages`
- [x] `id`
- [x] `digest_run_id`
- [x] `channel_id`
- [x] `provider`
- [x] `provider_message_id`
- [x] `payload_json`
- [x] `posted_at`

## Deliverables
- [x] Database initializes on first run
- [x] Tables and indexes are present
- [ ] Inserts and lookups work reliably

## Acceptance criteria
- [x] `python -m bl_news_digest.cli init-db` succeeds
- [ ] Dry run writes run metadata into SQLite

---

# Phase 4 - Source ingestion

## Objectives
Fetch raw content from the 3 MVP source groups.

## Tasks
- [ ] Implement a generic RSS fetcher that handles all 3 sources
- [ ] Store raw payloads before normalization
- [ ] Add timeouts and retries
- [ ] Add user agent headers

## Source-specific strategy

All 3 MVP sources use RSS. A single generic RSS fetcher handles all of them.

### BMAS RSS
- [ ] Use RSS parser
- [ ] Extract title, link, publication date, summary

### Bundestag RSS
- [ ] Use RSS parser
- [ ] Extract title, link, publication date, summary

### IAB RSS
- [ ] Use RSS parser
- [ ] Extract title, link, publication date, summary

## Deliverables
- [ ] All 3 MVP RSS sources can be fetched successfully
- [ ] Raw payloads are stored

## Acceptance criteria
- [ ] Each source adapter has a unit test with fixture data
- [ ] Fetch failures are retried and logged
- [ ] Raw items are persisted before parsing

---

# Phase 5 - Normalization and deduplication

## Objectives
Convert all source items into one common schema and remove duplicates.

## Tasks
- [ ] Normalize all items into one shared structure
- [ ] Canonicalize URLs
- [ ] Strip tracking parameters
- [ ] Compute title/content hashes
- [ ] Detect exact duplicates
- [ ] Detect near-duplicates using title similarity and text similarity
- [ ] Keep the highest-authority version of duplicate clusters

## Normalized item target shape

```python
{
    "source_id": "bmas_rss",
    "source_domain": "bmas.de",
    "url_original": "...",
    "url_canonical": "...",
    "title": "...",
    "summary": "...",
    "content_text": "...",
    "published_at": "...",
    "discovered_at": "...",
    "content_hash": "...",
    "rule_score": 0,
    "status": "new"
}
```

## Deduplication rules
- [ ] Exact URL duplicate -> collapse
- [ ] Exact content hash duplicate -> collapse
- [ ] Near-duplicate title/content similarity -> cluster
- [ ] Keep one canonical item per cluster

## Deliverables
- [ ] A working normalizer
- [ ] A working dedupe pipeline

## Acceptance criteria
- [ ] Known duplicates collapse consistently in tests
- [ ] Canonical URLs are stable across reruns

---

# Phase 6 - Rule-based filtering

## Objectives
Shortlist only externally relevant items before AI review.

## Tasks
- [ ] Create keyword allowlist covering AVGS, AZAV, labor-market activation, and coaching topics
- [ ] Check titles and summaries for any keyword match
- [ ] Pass any item with at least one keyword match to AI review
- [ ] Reject items with zero keyword matches before sending to AI
- [ ] Apply hard domain exclusions before keyword check

## Important filtering rule

Ignore ALL content originating from BeginnerLuft domains or channels.

Do NOT include:
- `beginnerluft.de`
- BeginnerLuft blog
- BeginnerLuft social media

## Suggested keyword categories

### Hard include terms
- [ ] `avgs`
- [ ] `aktivierungs- und vermittlungsgutschein`
- [ ] `§45 sgb iii`
- [ ] `maßnahme bei einem träger`
- [ ] `azav`

### Strong provider / compliance terms
- [ ] `trägerzulassung`
- [ ] `maßnahmezulassung`
- [ ] `fachkundige stelle`
- [ ] `akkreditierung`
- [ ] `coaching und aktivierung`

### Demand and market terms
- [ ] `jobcenter`
- [ ] `agentur für arbeit`
- [ ] `arbeitslos`
- [ ] `arbeitssuchend`
- [ ] `berufliche neuorientierung`
- [ ] `bewerbung`

### BeginnerLuft-fit context terms
- [ ] `burnout`
- [ ] `migration`
- [ ] `wiedereinstieg`
- [ ] `gründung`
- [ ] `karrierecoaching`

## Filter logic
- [ ] Any keyword match -> send to AI review
- [ ] No keyword match -> discard without AI call
- [ ] Hard exclusion domain -> always reject, regardless of keywords

## Deliverables
- [ ] Keyword allowlist covering all relevant topic categories
- [ ] Candidate shortlist passed to AI

## Acceptance criteria
- [ ] Obvious AVGS items pass
- [ ] Obvious noise items fail
- [ ] BeginnerLuft-owned URLs are always rejected

---

# Phase 7 - AI review and ranking

## Objectives
Use AI only on shortlisted items and store structured review results.

## Tasks
- [ ] Create JSON schema for per-item review
- [ ] Create a strict AI prompt that includes full BeginnerLuft company context
- [ ] Validate model output against schema using Pydantic
- [ ] Cache reviews by content hash to avoid re-reviewing unchanged items
- [ ] Use AI scores to rank items and select the top 5

## AI system prompt requirements

The system prompt must include three parts:

1. **BeginnerLuft company context** — enough for the model to reason about relevance without prior knowledge of the company.
2. **Task description** — review, score, and explain each item.
3. **Hard exclusion reminder** — BeginnerLuft-owned content is always irrelevant.

Example prompt structure:

```text
You are an intelligence analyst for BeginnerLuft, a Berlin-based career coaching provider.

## About BeginnerLuft
BeginnerLuft is an AVGS-certified coaching provider (AZAV-accredited). We offer career coaching
to job seekers, career changers, and professionals experiencing burnout or career breaks.
Our clients are referred via Jobcenter (SGB II) and Bundesagentur für Arbeit (SGB III) using
Aktivierungs- und Vermittlungsgutscheine (AVGS). Core coaching areas include career change,
burnout recovery, migration support, and entrepreneurship (Gründungsberatung).

## Your task
Review the following external news item and assess its relevance to BeginnerLuft.

IMPORTANT:
- Do NOT consider BeginnerLuft's own content as relevant.
- Only evaluate external signals that impact BeginnerLuft's business or operating environment.

Evaluate whether this item affects:
- AVGS rules, budget, or interpretation
- AZAV certification or accreditation requirements
- Jobcenter or BA procurement behavior
- Market demand for coaching services
- Competitive provider landscape
- Regulatory or legislative changes affecting SGB II / SGB III
```

## Required AI review schema fields
- [ ] `decision`
- [ ] `topic_type`
- [ ] `relevance_score`
- [ ] `beginnerluft_fit_score`
- [ ] `actionability_score`
- [ ] `business_impact_score`
- [ ] `urgency_score`
- [ ] `confidence`
- [ ] `summary`
- [ ] `why_relevant`
- [ ] `recommended_actions`

## Ranking logic
- [ ] Rank items by AI-assigned relevance score and other AI scores
- [ ] Enforce no duplicates in final top 5
- [ ] Limit overrepresentation from a single source in the final selection

## Deliverables
- [ ] Validated AI review pipeline
- [ ] Ranked top 5 candidate set

## Acceptance criteria
- [ ] Invalid AI output is retried or rejected cleanly
- [ ] Cached reviews prevent duplicate AI spend
- [ ] Final selection is stable and explainable

---

# Phase 8 - Slack rendering and posting

## Objectives
Render the daily digest to Slack Block Kit and post it into a fixed channel.

## Tasks
- [ ] Create a Slack client wrapper
- [ ] Render digest blocks from structured digest data
- [ ] Create fallback plain text message
- [ ] Implement dry-run mode without posting
- [ ] Store Slack response metadata in DB

## Required Slack digest structure
- [ ] Header block
- [ ] Context block with run stats
- [ ] Short editor note
- [ ] 5 ranked item sections
- [ ] Final action summary

## Per-item content requirements
Each item should show:
- [ ] headline
- [ ] source
- [ ] short summary
- [ ] why it matters for BeginnerLuft
- [ ] recommended action
- [ ] source URL

## Slack environment variables
- [ ] `SLACK_BOT_TOKEN`
- [ ] `SLACK_CHANNEL_ID`
- [ ] `SLACK_POST_ENABLED`

## Deliverables
- [ ] Valid Block Kit payload generator
- [ ] Working Slack post command

## Acceptance criteria
- [ ] Dry run prints payload without posting
- [ ] Live run posts successfully when enabled
- [ ] Posted message metadata is persisted

---

# Phase 9 - Local testing before deployment

## Objectives
Make the local project reliable before cloning it to Hetzner.

## Tasks
- [ ] Create unit tests for source parsers
- [ ] Create tests for normalization
- [ ] Create tests for dedupe logic
- [ ] Create tests for rule scoring
- [ ] Create tests for AI schema validation
- [ ] Create tests for Slack payload generation
- [ ] Create a full dry-run integration test

## Acceptance criteria
- [ ] Tests pass locally
- [ ] `python -m bl_news_digest.cli run --dry-run` works locally
- [ ] No real secrets are required for dry run

---

# Phase 10 - Deploy to Hetzner

## Objectives
Clone the repo on Hetzner, install dependencies, configure environment, and run the app manually once.

## Tasks
- [ ] SSH into Hetzner
- [ ] Choose deploy location, for example `~/apps/bl_news_digest`
- [ ] Clone GitHub repo onto Hetzner
- [ ] Create virtual environment on Hetzner
- [ ] Install dependencies
- [ ] Create production `.env`
- [ ] Initialize database
- [ ] Run one dry run
- [ ] Run one manual real run when ready

## Example Hetzner setup commands

```bash
mkdir -p ~/apps
cd ~/apps
git clone git@github.com:YOURNAME/bl_news_digest.git
cd bl_news_digest
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
cp .env.example .env
python -m bl_news_digest.cli init-db
python -m bl_news_digest.cli doctor
python -m bl_news_digest.cli run --dry-run
```

## Production `.env` guidance

On Hetzner, edit `.env` manually and replace placeholders with real values:
- [ ] real OpenAI API key
- [ ] real Slack bot token
- [ ] real Slack channel ID
- [ ] `SLACK_POST_ENABLED=true` only when ready
- [ ] `DRY_RUN=false` only when ready

## Acceptance criteria
- [ ] Repo is cloned successfully on Hetzner
- [ ] App installs successfully
- [ ] Dry run works on Hetzner

---

# Phase 11 - Cron setup on Hetzner

## Objectives
Run the digest daily automatically.

## Tasks
- [ ] Create cron entry for the daily run
- [ ] Redirect output to a log file
- [ ] Add a watchdog command if desired
- [ ] Verify cron environment behavior

## Recommended cron entry

```cron
15 6 * * * cd ~/apps/bl_news_digest && . .venv/bin/activate && python -m bl_news_digest.cli run >> logs/cron.log 2>&1
```

## Optional watchdog cron entry

```cron
15 7 * * * cd ~/apps/bl_news_digest && . .venv/bin/activate && python -m bl_news_digest.cli watchdog >> logs/cron.log 2>&1
```

## Acceptance criteria
- [ ] Cron triggers successfully
- [ ] Logs are written
- [ ] Digest posts to Slack on schedule when enabled

---

# Phase 12 - Update and deployment workflow after MVP exists

## Objectives
Use GitHub as source of truth and pull updates onto Hetzner cleanly.

## Recommended change workflow

### Local machine

```bash
git checkout main
git pull
action="Implement ranking improvements"
# make code changes locally
pytest
git add .
git commit -m "$action"
git push
```

### Hetzner server

```bash
cd ~/apps/bl_news_digest
git pull
source .venv/bin/activate
pip install -e .
python -m bl_news_digest.cli doctor
python -m bl_news_digest.cli run --dry-run
```

## Optional deploy script on Hetzner

Create `deploy.sh`:

```bash
#!/usr/bin/env bash
set -e
cd ~/apps/bl_news_digest
git pull
source .venv/bin/activate
pip install -e .
python -m bl_news_digest.cli doctor
```

Tasks:
- [ ] Create repeatable deploy procedure
- [ ] Avoid hot-editing production code directly

## Acceptance criteria
- [ ] Changes are made locally first
- [ ] Hetzner only receives deployed commits
- [ ] Deploy is repeatable and low-risk

---

# Phase 13 - Error handling, logging, and monitoring

## Objectives
Make failures visible and recoverable.

## Tasks
- [ ] Add structured logs for each pipeline stage
- [ ] Add clear exit codes
- [ ] Retry transient HTTP failures
- [ ] Log AI failures separately
- [ ] Detect empty digest scenarios
- [ ] Detect Slack posting failures
- [ ] Record alertable failures in DB

## Minimum alert conditions
- [ ] Daily run fails completely
- [ ] Slack post fails
- [ ] Zero candidates for multiple days in a row
- [ ] AI schema validation repeatedly fails

## Acceptance criteria
- [ ] Failures are visible in logs
- [ ] Critical steps have retry strategy
- [ ] Pipeline can fail gracefully without corrupting DB

---

# Phase 14 - Cost control

## Objectives
Keep AI usage efficient.

## Tasks
- [ ] Only send rule-passed items to AI
- [ ] Cache review results by content hash
- [ ] Truncate overly long content before sending to AI
- [ ] Use one compact review model for MVP
- [ ] Avoid re-reviewing unchanged items

## Acceptance criteria
- [ ] AI is called only for shortlisted items
- [ ] Same unchanged content does not trigger repeat AI calls

---

# Phase 15 - Definition of done for MVP

The MVP is done when all of the following are true:

- [ ] Local repo exists and is pushed to GitHub
- [ ] `.gitignore` is correct
- [ ] `.env.example` is committed
- [ ] `.env` is excluded from Git
- [ ] SQLite database is initialized automatically or by command
- [ ] Only the 3 MVP source groups are implemented
- [ ] BeginnerLuft-owned sources are excluded globally
- [ ] Fetch -> normalize -> dedupe -> rule-filter -> AI-review -> rank -> Slack-post flow works end-to-end
- [ ] Dry run works locally and on Hetzner
- [ ] Real Slack posting works on Hetzner
- [ ] Cron runs daily on Hetzner
- [ ] Logs and DB records make the pipeline auditable

---

## Appendix A - Future sources (NOT IMPLEMENTED IN MVP)

The following sources are intentionally excluded from Phase 1.

They can be added in a later phase.

### Tier 2 - Official extensions
- [ ] Bundesrat (XML)
- [ ] Gesetze-im-Internet
- [ ] Servicestelle SGB II
- [ ] BA Statistics API

### Tier 3 - Market and research
- [ ] DAkkS
- [ ] Regional BA / Jobcenter Berlin / Brandenburg

### Tier 4 - Media
- [ ] Tagesspiegel
- [ ] Bildungsklick
- [ ] Table.Media

Implementation rule:
- [ ] Do not implement appendix sources until the MVP has run stably for at least 1-2 weeks

---

## Appendix B - Files that must exist early

These files should exist very early in implementation:

- [ ] `.gitignore`
- [ ] `.env.example`
- [ ] `README.md`
- [ ] `pyproject.toml`
- [ ] `config/sources.yaml`
- [ ] `src/bl_news_digest/cli.py`
- [ ] `src/bl_news_digest/config.py`
- [ ] `src/bl_news_digest/db.py`

---

## Appendix C - Minimal command checklist

### Local machine
- [ ] `git init`
- [ ] `python3 -m venv .venv`
- [ ] `source .venv/bin/activate`
- [ ] `pip install -e .`
- [ ] `cp .env.example .env`
- [ ] `python -m bl_news_digest.cli doctor`
- [ ] `python -m bl_news_digest.cli init-db`
- [ ] `python -m bl_news_digest.cli run --dry-run`
- [ ] `git add . && git commit -m "..." && git push`

### Hetzner
- [ ] `git clone ...`
- [ ] `python3 -m venv .venv`
- [ ] `source .venv/bin/activate`
- [ ] `pip install -e .`
- [ ] `cp .env.example .env`
- [ ] edit `.env` manually
- [ ] `python -m bl_news_digest.cli init-db`
- [ ] `python -m bl_news_digest.cli doctor`
- [ ] `python -m bl_news_digest.cli run --dry-run`
- [ ] add cron job

