from __future__ import annotations

from bit_life_survival.app.ui import theme


def test_theme_catalog_has_nineteen_presets() -> None:
    names = theme.available_themes()
    assert len(names) == 19


def test_each_theme_applies_with_required_button_flat_color() -> None:
    for name in theme.available_themes():
        applied = theme.apply_theme(name)
        assert applied == name
        assert isinstance(theme.COLOR_BUTTON_FLAT, tuple)
        assert len(theme.COLOR_BUTTON_FLAT) == 3
        assert all(0 <= channel <= 255 for channel in theme.COLOR_BUTTON_FLAT)

