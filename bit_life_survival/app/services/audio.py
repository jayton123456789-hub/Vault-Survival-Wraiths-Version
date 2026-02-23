from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AudioService:
    master: float = 1.0
    music: float = 0.8
    sfx: float = 0.9

    def configure(self, master: float, music: float, sfx: float) -> None:
        self.master = max(0.0, min(1.0, float(master)))
        self.music = max(0.0, min(1.0, float(music)))
        self.sfx = max(0.0, min(1.0, float(sfx)))

    def play_click(self) -> None:
        # Stub for Phase 2. Audio hooks remain centralized here.
        return
