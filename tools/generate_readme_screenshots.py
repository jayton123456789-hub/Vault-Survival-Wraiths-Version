from __future__ import annotations

from pathlib import Path

import pygame

from bit_life_survival.app.scenes.base import BaseScene
from bit_life_survival.app.scenes.load_game import LoadGameScene
from bit_life_survival.app.scenes.menu import MainMenuScene
from bit_life_survival.app.scenes.operations import OperationsScene
from bit_life_survival.app.services.saves import SaveService
from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.backgrounds import BackgroundRenderer
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.models import EquippedSlots
from bit_life_survival.core.persistence import create_default_save_data, transfer_selected_citizen_to_roster
from bit_life_survival.core.settings import default_settings


class AppStub:
    def __init__(self, repo_root: Path) -> None:
        pygame.init()
        self.screen = pygame.Surface((1920, 1080))
        self.content = load_content(repo_root / "bit_life_survival" / "content")
        self.save_data = create_default_save_data(base_seed=2042)
        self.current_loadout = EquippedSlots()
        self.settings = default_settings()
        self.backgrounds = BackgroundRenderer()
        self.current_slot = 1

        saves_dir = repo_root / ".tmp_readme_saves"
        saves_dir.mkdir(parents=True, exist_ok=True)
        self.save_service = SaveService(saves_dir, slot_count=3)

        slot1 = self.save_service.create_new_game(slot=1, base_seed=2042)
        slot1.vault.tav = 28
        slot1.vault.vault_level = 2
        slot1.vault.upgrades["drone_bay_level"] = 1
        slot1.vault.last_run_distance = 14.8
        slot1.vault.last_run_time = 23
        self.save_service.save_slot(1, slot1)

        slot2 = self.save_service.create_new_game(slot=2, base_seed=3001)
        slot2.vault.tav = 7
        slot2.vault.last_run_distance = 5.4
        slot2.vault.last_run_time = 12
        self.save_service.save_slot(2, slot2)

        self.save_data = slot1

    def save_current_slot(self) -> None:
        if self.current_slot is not None and self.save_data is not None:
            self.save_service.save_slot(self.current_slot, self.save_data)

    def save_settings(self) -> None:
        return

    def virtual_mouse_pos(self) -> tuple[int, int]:
        return (0, 0)

    def compute_run_seed(self) -> int:
        return int(self.save_data.vault.settings.base_seed) + int(self.save_data.vault.run_counter)

    def change_scene(self, _scene) -> None:
        return

    def return_staged_loadout(self) -> None:
        return

    def quit(self) -> None:
        return


def _save(surface: pygame.Surface, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surface, str(path))


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    theme.apply_theme("ember")
    app = AppStub(repo_root)

    screenshots_dir = repo_root / "docs" / "screenshots"

    # Main menu
    menu = MainMenuScene()
    menu.render(app, app.screen)
    _save(app.screen, screenshots_dir / "main-menu.png")

    # Prep a drafted citizen for base + operations screenshots.
    drafted = transfer_selected_citizen_to_roster(app.save_data.vault, app.save_data.vault.citizen_queue[0].id)
    drafted.loadout.pack = "backpack_basic"
    drafted.loadout.armor = "armor_scrap"
    app.current_loadout = drafted.loadout.model_copy(deep=True)
    app.save_data.vault.current_citizen = drafted
    app.save_data.vault.active_deploy_citizen_id = drafted.id

    # Base command
    base = BaseScene()
    base.on_enter(app)
    base.render(app, app.screen)
    _save(app.screen, screenshots_dir / "base-command.png")

    # Operations loadout
    operations = OperationsScene(initial_tab="loadout")
    operations.on_enter(app)
    operations.render(app, app.screen)
    _save(app.screen, screenshots_dir / "operations-loadout.png")

    # Load game manager
    load_game = LoadGameScene()
    load_game.render(app, app.screen)
    _save(app.screen, screenshots_dir / "load-game.png")

    print(f"Saved screenshots to {screenshots_dir}")


if __name__ == "__main__":
    main()
