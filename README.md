# bl_news_digest

BeginnerLuft AVGS External News Digest — a daily Slack pipeline that fetches
official German labor-market RSS feeds, filters for AVGS relevance using
keywords, reviews shortlisted items with AI (GPT-4.1-mini), and posts a
ranked digest to a Slack channel.

## Sources (MVP)
- **BMAS** — Bundesministerium für Arbeit und Soziales RSS
- **Bundestag** — Ausschuss Arbeit und Soziales RSS
- **IAB** — Institut für Arbeitsmarkt- und Berufsforschung RSS

## Local setup

```bash
git clone git@github.com:YOURNAME/bl_news_digest.git
cd bl_news_digest
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edit .env and add real API keys when ready
```

## Commands

```bash
# Check configuration and environment
python -m bl_news_digest.cli doctor

# Initialise the SQLite database
python -m bl_news_digest.cli init-db

# List configured sources
python -m bl_news_digest.cli list-sources

# Run the pipeline in dry-run mode (no Slack post)
python -m bl_news_digest.cli run --dry-run

# Run the full pipeline
python -m bl_news_digest.cli run
```

## Run tests

```bash
pytest
```

## Deploy to Hetzner

```bash
# On the server (once)
mkdir -p ~/apps
cd ~/apps
git clone git@github.com:YOURNAME/bl_news_digest.git
cd bl_news_digest
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edit .env with real credentials
python -m bl_news_digest.cli init-db
python -m bl_news_digest.cli doctor
python -m bl_news_digest.cli run --dry-run

# Subsequent deploys
cd ~/apps/bl_news_digest
git pull
pip install -e .
python -m bl_news_digest.cli doctor
```

## Cron (Hetzner)

```cron
15 6 * * * cd ~/apps/bl_news_digest && . .venv/bin/activate && python -m bl_news_digest.cli run >> logs/cron.log 2>&1
```
