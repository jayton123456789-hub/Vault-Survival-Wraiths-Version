from __future__ import annotations

from pathlib import Path

from bit_life_survival.app.services import paths


def test_windows_primary_root_is_first_candidate(monkeypatch, tmp_path: Path) -> None:
    primary = tmp_path / "BitLifeSurvival"
    local = tmp_path / "LocalAppData"
    monkeypatch.setattr(paths, "PRIMARY_WINDOWS_ROOT", primary)
    monkeypatch.setattr(paths.os, "name", "nt", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local))

    roots = paths._candidate_roots(paths.APP_DIR_NAME)
    assert roots[0] == primary
    assert roots[1] == local / paths.APP_DIR_NAME


def test_resolve_user_paths_creates_runtime_directories(monkeypatch, tmp_path: Path) -> None:
    primary = tmp_path / "BitLifeSurvival"
    local = tmp_path / "LocalAppData"
    monkeypatch.setattr(paths, "PRIMARY_WINDOWS_ROOT", primary)
    monkeypatch.setattr(paths.os, "name", "nt", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local))

    resolved = paths.resolve_user_paths()
    assert resolved.root == primary
    assert resolved.saves.exists()
    assert resolved.logs.exists()
    assert resolved.config.exists()
