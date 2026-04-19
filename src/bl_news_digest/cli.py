from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
import yaml
from pydantic import ValidationError

logger = logging.getLogger(__name__)


@click.group()
def cli() -> None:
    """BeginnerLuft News Digest pipeline."""


@cli.command()
def doctor() -> None:
    """Validate configuration and environment."""
    from bl_news_digest.ops.logging_conf import configure_logging

    configure_logging()
    click.echo("=== bl-news-digest doctor ===\n")
    ok = True

    # 1. Config / env vars
    click.echo("[ ] Checking configuration...")
    try:
        from bl_news_digest.config import Settings

        s = Settings()
        click.echo(f"    app_env            : {s.app_env}")
        click.echo(f"    dry_run            : {s.dry_run}")
        click.echo(f"    log_level          : {s.log_level}")
        click.echo(f"    db_path            : {s.db_path}")
        click.echo(f"    openai_model       : {s.openai_model}")
        click.echo(f"    slack_channel_id   : {s.slack_channel_id}")
        click.echo(f"    slack_post_enabled : {s.slack_post_enabled}")
        click.echo(f"    digest_top_n       : {s.digest_top_n}")
        click.echo("[OK] Configuration loaded\n")
    except ValidationError as exc:
        click.echo(f"[FAIL] Configuration errors:\n{exc}\n", err=True)
        ok = False

    # 2. Sources YAML
    click.echo("[ ] Checking config/sources.yaml...")
    sources_path = Path("config/sources.yaml")
    if not sources_path.exists():
        click.echo(f"[FAIL] {sources_path} not found\n", err=True)
        ok = False
    else:
        try:
            with open(sources_path) as f:
                data = yaml.safe_load(f)
            sources = data.get("sources", [])
            enabled = [s for s in sources if s.get("enabled")]
            click.echo(f"    sources total   : {len(sources)}")
            click.echo(f"    sources enabled : {len(enabled)}")
            for src in enabled:
                click.echo(f"      - {src['id']} ({src['method']})")
            click.echo("[OK] Sources loaded\n")
        except Exception as exc:
            click.echo(f"[FAIL] Could not parse sources.yaml: {exc}\n", err=True)
            ok = False

    # 3. Data directory
    click.echo("[ ] Checking data/ directory...")
    data_dir = Path("data")
    if not data_dir.exists():
        click.echo("[WARN] data/ directory does not exist — run init-db to create it\n")
    else:
        click.echo("[OK] data/ directory exists\n")

    # Summary
    if ok:
        click.echo("=== All checks passed ===")
        sys.exit(0)
    else:
        click.echo("=== Some checks FAILED — see above ===", err=True)
        sys.exit(1)


@cli.command("init-db")
def init_db() -> None:
    """Initialise the SQLite database and create all tables."""
    from bl_news_digest.config import get_settings
    from bl_news_digest.db import init_database
    from bl_news_digest.ops.logging_conf import configure_logging

    configure_logging()
    settings = get_settings()
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_database(str(db_path))
    click.echo(f"Database initialised at {db_path.resolve()}")


@cli.command("list-sources")
def list_sources() -> None:
    """List all configured sources."""
    sources_path = Path("config/sources.yaml")
    if not sources_path.exists():
        click.echo("config/sources.yaml not found", err=True)
        sys.exit(1)

    with open(sources_path) as f:
        data = yaml.safe_load(f)

    sources = data.get("sources", [])
    click.echo(f"{'ID':<42} {'METHOD':<6} {'ENABLED':<8} PRIORITY")
    click.echo("-" * 65)
    for s in sources:
        click.echo(
            f"{s['id']:<42} {s['method']:<6} {str(s.get('enabled', False)):<8} {s.get('priority', '-')}"
        )


@cli.command()
@click.option(
    "--dry-run",
    "force_dry_run",
    is_flag=True,
    default=False,
    help="Force dry-run mode regardless of DRY_RUN env var.",
)
def run(force_dry_run: bool) -> None:
    """Run the full digest pipeline."""
    from bl_news_digest.config import get_settings
    from bl_news_digest.ops.logging_conf import configure_logging

    configure_logging()
    settings = get_settings()
    dry = force_dry_run or settings.dry_run
    click.echo(f"Starting digest pipeline (dry_run={dry})")
    click.echo("Pipeline not yet fully implemented — Phase 1 skeleton.")
    sys.exit(0)


if __name__ == "__main__":
    cli()
