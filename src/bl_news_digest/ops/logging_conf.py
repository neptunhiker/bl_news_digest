from __future__ import annotations

import logging
import sys
from pathlib import Path


def configure_logging(log_level: str = "INFO", log_dir: str = "logs") -> None:
    """Configure logging to stdout and an optional rotating file."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    fmt = "%(asctime)s %(levelname)-8s %(name)s  %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    log_path = Path(log_dir)
    if log_path.exists() or _try_mkdir(log_path):
        fh = logging.FileHandler(log_path / "app.log", encoding="utf-8")
        handlers.append(fh)

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers, force=True)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def _try_mkdir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False
