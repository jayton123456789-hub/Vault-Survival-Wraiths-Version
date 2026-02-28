from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.widgets import _fit_text_ellipsis


def test_fit_text_ellipsis_clamps_long_button_labels() -> None:
    pygame.init()
    font = theme.get_font(theme.FONT_SIZE_SECTION, bold=True, kind="display")
    text = "utility1: Extremely Long Equipment Name That Should Be Trimmed"
    fitted = _fit_text_ellipsis(font, text, 140)
    assert fitted
    assert fitted.endswith("...")
    assert font.size(fitted)[0] <= 140
