from __future__ import annotations

import logging
import traceback
from pathlib import Path

import pygame

from bit_life_survival.app.scenes.core import Scene
from bit_life_survival.app.scenes.intro import IntroScene
from bit_life_survival.app.services.audio import AudioService
from bit_life_survival.app.services.saves import SaveService
from bit_life_survival.app.services.settings_store import SettingsStore
from bit_life_survival.app.ui import theme
from bit_life_survival.core.loader import ContentValidationError, load_content
from bit_life_survival.core.models import EquippedSlots
from bit_life_survival.core.persistence import store_item


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _configure_logging(repo_root: Path) -> tuple[logging.Logger, Path]:
    logs_dir = repo_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "latest.log"

    logger = logging.getLogger("bit_life_survival")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(sh)
    logger.addHandler(fh)
    return logger, log_path


class GameApp:
    def __init__(self) -> None:
        self.repo_root = _repo_root()
        self.logger, self.log_path = _configure_logging(self.repo_root)
        self.logger.info("Starting Bit Life Survival...")
        print("Starting Bit Life Survival...")

        self.content = self._load_content()
        self.settings_store = SettingsStore(self.repo_root / "settings.json")
        self.settings = self.settings_store.load()
        self.save_service = SaveService(self.repo_root)
        self.audio = AudioService()
        self.audio.configure(
            self.settings["audio"]["master"],
            self.settings["audio"]["music"],
            self.settings["audio"]["sfx"],
        )

        self.current_slot: int | None = None
        self.save_data = None
        self.current_loadout = EquippedSlots()

        self.assets_intro_dir = self.repo_root / "bit_life_survival" / "assets" / "bbwg_intro"

        self.running = True
        self.quit_after_scene = False
        self.scene: Scene | None = None

        pygame.init()
        self.clock = pygame.time.Clock()
        self.screen = pygame.display.set_mode(theme.DEFAULT_RESOLUTION, pygame.RESIZABLE)
        pygame.display.set_caption(theme.WINDOW_TITLE)
        self.apply_video_settings()

    def _load_content(self):
        content_dir = self.repo_root / "bit_life_survival" / "content"
        try:
            return load_content(content_dir)
        except ContentValidationError:
            self.logger.exception("Failed to load content.")
            raise SystemExit(1)

    def save_settings(self) -> None:
        self.settings_store.save(self.settings)

    def apply_video_settings(self) -> None:
        video = self.settings["video"]
        resolution = tuple(video.get("resolution", [1280, 720]))
        fullscreen = bool(video.get("fullscreen", False))
        flags = pygame.RESIZABLE
        if fullscreen:
            flags |= pygame.FULLSCREEN
        self.screen = pygame.display.set_mode(resolution, flags)
        pygame.display.set_caption(theme.WINDOW_TITLE)

    def load_slot(self, slot: int) -> None:
        self.return_staged_loadout()
        self.save_data = self.save_service.load_slot(slot)
        self.current_slot = slot
        self.current_loadout = EquippedSlots()
        # Keep per-slot intro skip in sync with global setting.
        self.save_data.vault.settings.skip_intro = bool(self.settings["gameplay"].get("skip_intro", False))
        self.save_current_slot()
        self.logger.info("Loaded slot %s", slot)

    def new_slot(self, slot: int, base_seed: int = 1337) -> None:
        self.return_staged_loadout()
        self.save_data = self.save_service.create_new_game(slot=slot, base_seed=base_seed)
        self.current_slot = slot
        self.current_loadout = EquippedSlots()
        self.save_data.vault.settings.skip_intro = bool(self.settings["gameplay"].get("skip_intro", False))
        self.save_current_slot()
        self.logger.info("Created new game in slot %s", slot)

    def save_current_slot(self) -> None:
        if self.current_slot is None or self.save_data is None:
            return
        self.save_service.save_slot(self.current_slot, self.save_data)

    def compute_run_seed(self) -> int:
        if self.save_data is None:
            return 1337
        settings = self.save_data.vault.settings
        if settings.seeded_mode:
            return int(settings.base_seed) + int(self.save_data.vault.run_counter)
        return int(pygame.time.get_ticks() & 0xFFFFFFFF)

    def return_staged_loadout(self) -> None:
        if self.save_data is None:
            return
        for item_id in self.current_loadout.as_values():
            store_item(self.save_data.vault, item_id, 1)
        self.current_loadout = EquippedSlots()
        self.save_current_slot()

    def change_scene(self, scene: Scene) -> None:
        if self.scene is not None:
            self.scene.on_exit(self)
        self.scene = scene
        self.scene.on_enter(self)

    def quit(self) -> None:
        self.running = False

    def run(self) -> None:
        self.change_scene(IntroScene())
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            try:
                for event in pygame.event.get():
                    if self.scene is not None:
                        self.scene.handle_event(self, event)
                if self.scene is not None:
                    self.scene.update(self, dt)
                    self.scene.render(self, self.screen)
                pygame.display.flip()
            except Exception:
                self.logger.error("Unhandled runtime exception:\n%s", traceback.format_exc())
                print(f"Fatal error. See log: {self.log_path}")
                break

        try:
            self.return_staged_loadout()
        except Exception:
            self.logger.exception("Failed returning staged loadout during shutdown.")
        pygame.quit()


def main() -> None:
    app = GameApp()
    app.run()


if __name__ == "__main__":
    main()
