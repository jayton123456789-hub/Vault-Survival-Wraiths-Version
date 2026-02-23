# Phase 1 Vertical Slice

## Scope
Phase 1 delivers a playable Python desktop slice with this loop:

`Base -> Claw Draft -> Loadout -> Run -> Death -> Drone Recovery -> Vault Progress -> Repeat`

This phase is Python-only and data-driven (`bit_life_survival/content/*.json`).

## Stack
- Python 3.11+
- `pydantic` for runtime validation
- `rich` for terminal UI/HUD
- `typer` for CLI tooling
- `pytest` for tests
- `pygame` for BBWG intro playback

## Setup
1. Create venv:
   - `py -3.11 -m venv .venv`
2. Activate:
   - `.venv\Scripts\activate`
3. Install deps:
   - `python -m pip install -r requirements.txt`

## Run App
- `python -m bit_life_survival.app.main`

Or one-click launcher:
- `tools\run_game.cmd`

## Install Desktop Shortcut
- `powershell -ExecutionPolicy Bypass -File tools\install_shortcut.ps1`

This creates Desktop shortcut: `Bit Life Survival.lnk`.

## Run Simulator
- `python -m bit_life_survival.tools.simulate --seed 123 --steps 50 --biome suburbs --autopick safe`

Autopick policies:
- `safe`: lowest death-chance unlocked option (or first unlocked)
- `random`: deterministic seeded random unlocked option
- `greedy`: prioritize loot-bearing options

## Run Tests
- `python -m pytest -q`

## Notes
- Save file is `save.json` at repo root.
- Intro settings can be toggled in Base -> Settings, in `settings.json`, or via `BLS_SKIP_INTRO=1`.
