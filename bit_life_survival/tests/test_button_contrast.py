from __future__ import annotations

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.widgets import _best_contrast_text


def _channel_luminance(channel: int) -> float:
    value = float(channel) / 255.0
    if value <= 0.03928:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _relative_luminance(color: tuple[int, int, int]) -> float:
    return (
        0.2126 * _channel_luminance(color[0])
        + 0.7152 * _channel_luminance(color[1])
        + 0.0722 * _channel_luminance(color[2])
    )


def _contrast_ratio(foreground: tuple[int, int, int], background: tuple[int, int, int]) -> float:
    lum_fg = _relative_luminance(foreground)
    lum_bg = _relative_luminance(background)
    bright = max(lum_fg, lum_bg)
    dark = min(lum_fg, lum_bg)
    return (bright + 0.05) / (dark + 0.05)


def test_button_labels_keep_minimum_contrast_across_themes() -> None:
    for theme_name in theme.available_themes():
        theme.apply_theme(theme_name)
        text_color = _best_contrast_text(theme.COLOR_BUTTON_FLAT)
        ratio = _contrast_ratio(text_color, theme.COLOR_BUTTON_FLAT)
        assert ratio >= 4.5, f"{theme_name} button contrast too low: {ratio:.2f}"
