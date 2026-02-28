from __future__ import annotations

from .core import Scene


class StorageScene(Scene):
    """Backward-compatible route into Operations Hub storage tab."""

    def on_enter(self, app) -> None:
        from .operations import OperationsScene

        app.change_scene(OperationsScene(initial_tab="storage"))
