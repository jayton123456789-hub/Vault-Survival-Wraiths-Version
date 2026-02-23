from __future__ import annotations

import json
from pathlib import Path

from .models import VaultState


def create_default_vault_state() -> VaultState:
    return VaultState()


def load_vault_state(save_path: Path | str = "save.json") -> VaultState:
    path = Path(save_path)
    if not path.exists():
        return create_default_vault_state()
    data = json.loads(path.read_text(encoding="utf-8"))
    return VaultState.model_validate(data)


def save_vault_state(state: VaultState, save_path: Path | str = "save.json") -> None:
    path = Path(save_path)
    path.write_text(json.dumps(state.model_dump(mode="json"), indent=2), encoding="utf-8")
