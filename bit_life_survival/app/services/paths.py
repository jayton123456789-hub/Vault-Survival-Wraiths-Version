from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_DIR_NAME = "BitLifeSurvival"


@dataclass(slots=True)
class UserPaths:
    root: Path
    saves: Path
    logs: Path
    config: Path


def resolve_user_paths(app_name: str = APP_DIR_NAME) -> UserPaths:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / "AppData" / "Local"

    root = base / app_name
    saves = root / "saves"
    logs = root / "logs"
    config = root / "config"

    saves.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    config.mkdir(parents=True, exist_ok=True)

    return UserPaths(root=root, saves=saves, logs=logs, config=config)
