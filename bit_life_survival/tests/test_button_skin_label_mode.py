from __future__ import annotations

import pygame

from bit_life_survival.app.ui import button_skins


def test_skin_label_matching_allows_exact_button_art_labels() -> None:
    assert button_skins.skin_matches_label("new_game", "New Game") is True
    assert button_skins.skin_matches_label("use_the_claw", "Use The Claw") is True


def test_skin_label_matching_blocks_mismatched_embedded_text() -> None:
    assert button_skins.skin_matches_label("mission", "Mission") is False
    assert button_skins.skin_matches_label("vault", "Vault") is False
    assert button_skins.skin_matches_label("continue", "Continue Until Next Event") is False


def test_frame_text_mode_allows_semantic_reuse_without_embedded_label_match() -> None:
    pygame.init()
    pygame.display.set_mode((16, 16))
    surface = button_skins.get_button_surface("mission", (256, 64), hovered=False, enabled=True, render_mode="frame_text")
    assert surface is not None
