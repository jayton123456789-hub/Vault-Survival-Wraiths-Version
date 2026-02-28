from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GameplaySettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    skip_intro: bool = False
    show_advanced_overlay: bool = False
    confirm_retreat: bool = True
    save_slots: int = Field(default=3, ge=3, le=5)
    tutorial_completed: bool = False
    replay_tutorial: bool = False
    vault_assistant_enabled: bool = True
    vault_assistant_stage: int = Field(default=0, ge=0, le=3)
    vault_assistant_completed: bool = False
    replay_vault_assistant: bool = False
    vault_assistant_tav_briefed: bool = False
    base_seed: int = 1337
    show_tooltips: bool = True


class VideoSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fullscreen: bool = True
    resolution: list[int] = Field(default_factory=lambda: [1280, 720], min_length=2, max_length=2)
    ui_scale: float = Field(default=1.0, ge=0.75, le=1.5)
    vsync: bool = False
    ui_theme: str = "ember"


class AudioSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    master: float = Field(default=1.0, ge=0.0, le=1.0)
    music: float = Field(default=0.8, ge=0.0, le=1.0)
    sfx: float = Field(default=0.9, ge=0.0, le=1.0)


class ControlSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    continue_key: str = Field(default="C", alias="continue")
    log: str = "L"
    retreat: str = "R"
    quit: str = "Q"
    help: str = "H"


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    gameplay: GameplaySettings = Field(default_factory=GameplaySettings)
    video: VideoSettings = Field(default_factory=VideoSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    controls: ControlSettings = Field(default_factory=ControlSettings)

    def as_dict(self) -> dict[str, Any]:
        return json.loads(self.model_dump_json(by_alias=True))


def merge_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    return AppSettings.model_validate(payload).as_dict()


def default_settings() -> dict[str, Any]:
    return AppSettings().as_dict()
