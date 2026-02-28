# Bit Life Survival

Python roguelite prototype with deterministic run simulation, data-driven content, and a playable pygame window UI.

## Windows Install
Install path and user-data path are separated:
- Repo install target: `C:\BitLifeSurvival\Vault_Bit_Survival\`
- Runtime data (default): `C:\BitLifeSurvival\`
  - Saves: `C:\BitLifeSurvival\saves`
  - Logs: `C:\BitLifeSurvival\logs`
  - Config: `C:\BitLifeSurvival\config`
- Automatic fallback order if `C:\BitLifeSurvival` is unavailable:
  1. `%LOCALAPPDATA%\BitLifeSurvival`
  2. `%USERPROFILE%\BitLifeSurvival`

Run installer/move helper:
- `powershell -ExecutionPolicy Bypass -File scripts\windows_install.ps1`
- `powershell -ExecutionPolicy Bypass -File tools\install_to_c.ps1`

## Quickstart
1. Create venv:
   - `py -3.11 -m venv .venv`
2. Install dependencies:
   - `.venv\Scripts\python -m pip install -r requirements.txt`
3. Run game:
   - `.venv\Scripts\python -m bit_life_survival.app.main`

Flow:
- Intro -> Main Menu -> New/Load -> Base -> Operations Hub (Loadout/Inventory/Storage/Crafting tabs) -> Briefing -> Run -> Event/Result -> Death/Retreat report

## Core Controls
- Base: `U` use claw, `Enter` draft selected, `L` Operations, `D` Deploy, `B` Drone Bay, `S` Settings, `H` Help.
- Operations Hub tabs: click `Loadout / Inventory / Storage / Crafting` (top tabs).
- Operations actions: `B` equip best, `A` equip all, `D` deploy, `Esc` back.
- Run: `C` continue, `L` log, `R` retreat, `E` use aid, `Q` quit, `H` help.

## One-Click Launcher
- `tools\run_game.cmd`

## Desktop Shortcut
- `powershell -ExecutionPolicy Bypass -File tools\install_shortcut.ps1`

## CLI Simulator
- `.venv\Scripts\python -m bit_life_survival.tools.simulate --seed 123 --steps 50 --biome suburbs --autopick safe`

## Tests
- `.venv\Scripts\python -m pytest -q`
- Smoke run:
  - `.venv\Scripts\python -m bit_life_survival.app.main`

## Docs
- `docs/PHASE1_VERTICAL_SLICE.md`
- `docs/INTRO_BBWG.md`
- `docs/PHASE0_FOUNDATION.md`
