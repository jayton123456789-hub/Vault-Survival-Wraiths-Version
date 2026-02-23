# Bit Life Survival

Python roguelite prototype with deterministic run simulation, data-driven content, and a playable pygame window UI.

## Quickstart
1. Create venv:
   - `py -3.11 -m venv .venv`
2. Install dependencies:
   - `.venv\Scripts\python -m pip install -r requirements.txt`
3. Run game:
   - `.venv\Scripts\python -m bit_life_survival.app.main`

Flow:
- Intro -> Main Menu -> New/Load -> Base -> Loadout -> Run -> Event/Result -> Death/Retreat report

## One-Click Launcher
- `tools\run_game.cmd`

## Desktop Shortcut
- `powershell -ExecutionPolicy Bypass -File tools\install_shortcut.ps1`

## CLI Simulator
- `.venv\Scripts\python -m bit_life_survival.tools.simulate --seed 123 --steps 50 --biome suburbs --autopick safe`

## Tests
- `.venv\Scripts\python -m pytest -q`

## Docs
- `docs/PHASE1_VERTICAL_SLICE.md`
- `docs/INTRO_BBWG.md`
- `docs/PHASE0_FOUNDATION.md`
