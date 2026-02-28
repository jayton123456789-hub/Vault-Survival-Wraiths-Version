from __future__ import annotations

import os
from pathlib import Path

import pygame

from bit_life_survival.app.scenes.core import Scene
from bit_life_survival.app.scenes.intro import IntroScene
from bit_life_survival.app.services.audio import AudioService
from bit_life_survival.app.services.logger import configure_logging
from bit_life_survival.app.services.paths import resolve_user_paths
from bit_life_survival.app.services.saves import SaveService
from bit_life_survival.app.services.settings_store import SettingsStore
from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.backgrounds import BackgroundRenderer
from bit_life_survival.app.ui.pixel_renderer import PixelRenderer
from bit_life_survival.app.ui.widgets import wrap_text
from bit_life_survival.core.loader import ContentValidationError, load_content
from bit_life_survival.core.models import EquippedSlots
from bit_life_survival.core.persistence import store_item


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class GameApp:
    def __init__(self) -> None:
        self.repo_root = _repo_root()
        self.user_paths = resolve_user_paths()
        logger_bundle = configure_logging(self.user_paths.logs)
        self.logger = logger_bundle.app
        self.gameplay_logger = logger_bundle.gameplay
        self.log_path = logger_bundle.latest_log_path
        self.logger.info("Starting Bit Life Survival...")
        print("Starting Bit Life Survival...")

        self.content = self._load_content()
        self.settings_store = SettingsStore(self.user_paths.config / "settings.json")
        self.settings = self.settings_store.load()
        self.settings["video"]["ui_theme"] = theme.apply_theme(self.settings["video"].get("ui_theme", theme.DEFAULT_THEME))
        theme.set_font_scale(float(self.settings["video"].get("ui_scale", 1.0)))
        slot_count = int(self.settings.get("gameplay", {}).get("save_slots", 3))
        self.save_service = SaveService(self.user_paths.saves, slot_count=slot_count)
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
        self.backgrounds = BackgroundRenderer()

        self.running = True
        self.quit_after_scene = False
        self.scene: Scene | None = None

        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        pygame.init()
        self.clock = pygame.time.Clock()
        self.pixel_renderer = PixelRenderer(
            virtual_width=theme.VIRTUAL_RESOLUTION[0],
            virtual_height=theme.VIRTUAL_RESOLUTION[1],
        )
        self.window = pygame.display.set_mode(theme.DEFAULT_RESOLUTION, pygame.RESIZABLE)
        self.pixel_renderer.set_window_size(self.window.get_size())
        self.screen = self.pixel_renderer.create_canvas()
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

    def apply_theme(self) -> None:
        selected = self.settings["video"].get("ui_theme", theme.DEFAULT_THEME)
        applied = theme.apply_theme(selected)
        self.settings["video"]["ui_theme"] = applied

    def _sync_vault_ui_settings(self) -> None:
        if self.save_data is None:
            return
        vault_settings = self.save_data.vault.settings
        vault_settings.theme_preset = self.settings["video"].get("ui_theme", theme.DEFAULT_THEME)
        vault_settings.font_scale = float(self.settings["video"].get("ui_scale", 1.0))
        vault_settings.show_tooltips = bool(self.settings["gameplay"].get("show_tooltips", True))

    def apply_video_settings(self) -> None:
        self.apply_theme()
        video = self.settings["video"]
        theme.set_font_scale(float(video.get("ui_scale", 1.0)))
        fullscreen = bool(video.get("fullscreen", True))
        if fullscreen:
            resolution = (0, 0)
            flags = pygame.FULLSCREEN
        else:
            resolution = tuple(video.get("resolution", list(theme.DEFAULT_RESOLUTION)))
            flags = pygame.RESIZABLE
        self.window = pygame.display.set_mode(resolution, flags)
        self.pixel_renderer.set_window_size(self.window.get_size())
        self.screen = self.pixel_renderer.create_canvas()
        pygame.display.set_caption(theme.WINDOW_TITLE)

    def virtual_mouse_pos(self) -> tuple[int, int]:
        return self.pixel_renderer.window_to_virtual(pygame.mouse.get_pos())

    def load_slot(self, slot: int) -> None:
        self.return_staged_loadout()
        self.save_data = self.save_service.load_slot(slot)
        self.current_slot = slot
        self.current_loadout = EquippedSlots()
        # Keep per-slot intro skip in sync with global setting.
        self.save_data.vault.settings.skip_intro = bool(self.settings["gameplay"].get("skip_intro", False))
        self._sync_vault_ui_settings()
        self.save_current_slot()
        self.logger.info("Loaded slot %s", slot)

    def new_slot(self, slot: int, base_seed: int = 1337) -> None:
        self.return_staged_loadout()
        self.save_data = self.save_service.create_new_game(slot=slot, base_seed=base_seed)
        self.current_slot = slot
        self.current_loadout = EquippedSlots()
        self.save_data.vault.settings.skip_intro = bool(self.settings["gameplay"].get("skip_intro", False))
        self._sync_vault_ui_settings()
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

    def _render_crash_modal(self, surface: pygame.Surface, message: str) -> None:
        surface.fill((8, 8, 12))
        modal = pygame.Rect(surface.get_width() // 2 - 420, surface.get_height() // 2 - 170, 840, 340)
        pygame.draw.rect(surface, (28, 32, 42), modal, border_radius=10)
        pygame.draw.rect(surface, (196, 92, 92), modal, width=2, border_radius=10)

        title = theme.get_font(34, bold=True).render("The game hit an error", True, (245, 218, 218))
        surface.blit(title, (modal.left + 20, modal.top + 20))

        body_font = theme.get_font(20)
        lines = [
            message.strip() or "Unexpected runtime error.",
            f"Log saved to: {self.log_path}",
            "Press Enter or Esc to quit safely.",
        ]
        y = modal.top + 88
        for raw in lines:
            for line in wrap_text(raw, body_font, modal.width - 40):
                rendered = body_font.render(line, True, (220, 224, 236))
                surface.blit(rendered, (modal.left + 20, y))
                y += 28
            y += 6

    def _show_crash_modal(self, message: str) -> None:
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    waiting = False
                elif event.type == pygame.KEYDOWN and event.key in {pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_q}:
                    waiting = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    waiting = False
            self._render_crash_modal(self.screen, message)
            self.pixel_renderer.present(self.window, self.screen)
            pygame.display.flip()
            self.clock.tick(30)

    def run(self) -> None:
        self.change_scene(IntroScene())
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            try:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.quit()
                        continue
                    if event.type == pygame.WINDOWRESIZED:
                        self.pixel_renderer.set_window_size((event.x, event.y))
                    if self.scene is not None:
                        self.scene.handle_event(self, self.pixel_renderer.transform_event(event))
                if self.scene is not None:
                    self.backgrounds.update(dt)
                    self.scene.update(self, dt)
                    self.scene.render(self, self.screen)
                self.pixel_renderer.present(self.window, self.screen)
                pygame.display.flip()
            except Exception as exc:  # noqa: BLE001
                self.logger.exception("Unhandled runtime exception")
                print(f"Fatal error. See log: {self.log_path}")
                self._show_crash_modal(str(exc))
                self.running = False

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
