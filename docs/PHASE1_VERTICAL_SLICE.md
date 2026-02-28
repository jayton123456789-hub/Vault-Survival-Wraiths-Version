# Phase 2.1 Window Slice

## Scope
Playable pygame desktop loop:

`Main Menu -> Base -> Operations Hub -> Briefing -> Run -> Death/Retreat -> Drone Recovery -> Base`

Python-only, data-driven content from `bit_life_survival/content/*.json`.

## Stack
- Python 3.11+
- `pydantic` for runtime validation
- `rich` for terminal UI/HUD
- `typer` for CLI tooling
- `pytest` for tests
- `pygame` for intro + full window UI

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

Smoke command:
- `python -m bit_life_survival.app.main`

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

## Data Paths (Windows)
- Default runtime root: `C:\BitLifeSurvival\`
- Saves: `C:\BitLifeSurvival\saves`
- Config: `C:\BitLifeSurvival\config\settings.json`
- Logs: `C:\BitLifeSurvival\logs\latest.log`
- Fallback chain (automatic): `%LOCALAPPDATA%\BitLifeSurvival` then `%USERPROFILE%\BitLifeSurvival`

## Renderer
- The pygame UI now uses a virtual canvas and blits to the window each frame.
- Virtual resolution constant: `bit_life_survival/app/ui/theme.py::VIRTUAL_RESOLUTION`
- Mouse input is remapped from window space into virtual-canvas space.

## Controls
- Base: `U` claw draft, `Enter` draft selected, `L` operations hub, `D` deploy, `B` drone bay, `S` settings, `H` help.
- Operations Hub: top tabs `Loadout / Inventory / Storage / Crafting`, `B` equip best, `A` equip all, `D` deploy, `Esc` back.
- Run: `C` continue, `L` log toggle, `R` retreat, `E` use aid, `Q` quit, `H` help.
- Event modal: `1-4` choose option, `R` retreat, `Q` quit, `H` help.

## Retreat Behavior
- Retreat ends the run immediately and marks a recovery penalty (`retreated_early`).
- Drone recovery still runs on current inventory + equipped gear before returning to base.

## Tutorial and Help
- First run shows guided tutorial overlay on Run screen.
- Settings has `Replay Tutorial (next run)`.
- Structured help overlays are available on Base, Loadout, and Run.

## Intro Red Overlay Tuning
In `bit_life_survival/app/intro.py`:
- `RED_OVERLAY_ALPHA_SHAKE` controls impact-frame red intensity.
- `RED_OVERLAY_ALPHA_POST` controls post-shake/hold red glow.

Lower values reduce red tint. Set `RED_OVERLAY_ALPHA_POST = 0` to effectively remove post-shake red.
