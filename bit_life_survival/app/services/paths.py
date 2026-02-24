from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_DIR_NAME = "BitLifeSurvival"
PRIMARY_WINDOWS_ROOT = Path(r"C:\BitLifeSurvival")


@dataclass(slots=True)
class UserPaths:
    root: Path
    saves: Path
    logs: Path
    config: Path


def _candidate_roots(app_name: str) -> list[Path]:
    candidates: list[Path] = []
    if os.name == "nt":
        candidates.append(PRIMARY_WINDOWS_ROOT)

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / app_name)

    candidates.append(Path.home() / app_name)
    return candidates


def resolve_user_paths(app_name: str = APP_DIR_NAME) -> UserPaths:
    last_error: Exception | None = None
    for root in _candidate_roots(app_name):
        saves = root / "saves"
        logs = root / "logs"
        config = root / "config"
        try:
            saves.mkdir(parents=True, exist_ok=True)
            logs.mkdir(parents=True, exist_ok=True)
            config.mkdir(parents=True, exist_ok=True)
            return UserPaths(root=root, saves=saves, logs=logs, config=config)
        except OSError as exc:
            last_error = exc
            continue
    raise RuntimeError("Unable to initialize user data directories.") from last_error
