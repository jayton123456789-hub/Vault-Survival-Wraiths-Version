# Vault Survival - Wraith's Version

A polished **pygame roguelite prototype** with deterministic runs, persistent save slots, a new research-driven progression loop, and a rebuilt run UX.

---

## Screenshots

### Main Command
![Main Menu](docs/screenshots/main-menu.png)

### Base Operations Deck
![Base Command](docs/screenshots/base-command.png)

### Operations Loadout + Gear UX
![Operations Loadout](docs/screenshots/operations-loadout.png)

### Save Slot Manager (Load + Delete)
![Load Game](docs/screenshots/load-game.png)

---

## Full Sweep Overhaul

This branch now includes:

1. **No-retreat run flow** in the standard loop. Runs now push toward extraction checkpoints instead of retreating early.
2. **Field inventory overlay** with consumables, gear summary, stats, and mission progress (`I` in-run).
3. **Hunger system** layered into the run loop with less oppressive dehydration pacing.
4. **Research Command scene** with five branches, dependencies, max level 5, and scrap-based costs that rise by `+20` each level.
5. **Deployment starts at exactly one runner** and expands later through research.
6. **Field contracts unlock later** through research instead of appearing immediately.
7. **Drone recovery redesign** with a ~20% baseline for carried loot, deeper-run risk, and clearer recovered vs lost reporting.
8. **Runner state fixes** so dead runners are moved out of deploy-ready paths and never appear ready in the bay.
9. **Stronger mission clarity** in Base, Briefing, Run, and result screens.
10. **Updated progression pacing** centered on finishing the campaign through research + TAV growth.

---

## Core Flow

`Intro -> Main Menu -> New/Load -> Base -> Research / Operations / Drone Bay -> Briefing -> Run -> Result`

---

## Quickstart (Windows)

1. Create venv
   - `py -3.11 -m venv .venv`
2. Install deps
   - `.venv\Scripts\python -m pip install -r requirements.txt`
3. Run game
   - `.venv\Scripts\python -m bit_life_survival.app.main`

---

## Controls

### Base
- `U` Use The Claw
- `Enter` Draft Selected
- `L` Operations
- `R` Research
- `D` Deploy
- `B` Drone Bay
- `S` Settings
- `H` Help

### Operations
- Top tabs: `Loadout / Equippable / Storage / Crafting`
- Actions: `E` Equip Selected, `B` Equip Best, `A` Equip All, `D` Deploy, `Esc` Back

### Run
- `C` Continue
- `L` Log
- `I` Inventory
- `E` Quick Aid
- `X` Extract
- `Q` Quit
- `H` Help

---

## Utility Scripts

- One-click launcher: `tools\run_game.cmd`
- Desktop shortcut installer: `powershell -ExecutionPolicy Bypass -File tools\install_shortcut.ps1`
- Screenshot generator (README assets):
  - `.venv\Scripts\python tools\generate_readme_screenshots.py`

---

## Data Paths (Windows)

- Install target: `C:\BitLifeSurvival\Vault_Bit_Survival\`
- Runtime data default: `C:\BitLifeSurvival\`
  - Saves: `C:\BitLifeSurvival\saves`
  - Logs: `C:\BitLifeSurvival\logs`
  - Config: `C:\BitLifeSurvival\config`

Fallback order when `C:\BitLifeSurvival` is unavailable:
1. `%LOCALAPPDATA%\BitLifeSurvival`
2. `%USERPROFILE%\BitLifeSurvival`

---

## Docs

- `docs/PHASE1_VERTICAL_SLICE.md`
- `docs/INTRO_BBWG.md`
- `docs/PHASE0_FOUNDATION.md`
