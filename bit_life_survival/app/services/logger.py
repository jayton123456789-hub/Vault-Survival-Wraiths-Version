from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class AppLoggerBundle:
    app: logging.Logger
    gameplay: logging.Logger
    latest_log_path: Path


def _rotate_latest_log(logs_dir: Path, keep_archives: int = 5) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    latest = logs_dir / "latest.log"
    if latest.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived = logs_dir / f"latest_{stamp}.log"
        latest.replace(archived)

    archives = sorted(
        [path for path in logs_dir.glob("latest_*.log") if path.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for stale in archives[keep_archives:]:
        stale.unlink(missing_ok=True)
    return latest


def configure_logging(logs_dir: Path) -> AppLoggerBundle:
    latest = _rotate_latest_log(logs_dir)
    gameplay_log_path = logs_dir / "gameplay.log"

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    app_logger = logging.getLogger("bit_life_survival")
    app_logger.setLevel(logging.INFO)
    app_logger.handlers.clear()
    app_logger.propagate = False

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(latest, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)

    app_logger.addHandler(stream_handler)
    app_logger.addHandler(file_handler)

    gameplay_logger = logging.getLogger("bit_life_survival.gameplay")
    gameplay_logger.setLevel(logging.INFO)
    gameplay_logger.handlers.clear()
    gameplay_logger.propagate = False

    gameplay_handler = logging.FileHandler(gameplay_log_path, mode="w", encoding="utf-8")
    gameplay_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    gameplay_logger.addHandler(gameplay_handler)

    return AppLoggerBundle(app=app_logger, gameplay=gameplay_logger, latest_log_path=latest)
