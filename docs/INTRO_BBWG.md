# BBWG Studio Intro Integration

## Source Guide
Integrated from:
- `C:\Users\nickb\Downloads\Compressed\BBWG\BBWG\BBWG_Studio_Intro_Guide.txt`

## Copied Assets
Copied into repo-local runtime path `bit_life_survival/assets/bbwg_intro/`:
- `LOGOframe1.png`
- `LOGOframe2.png`
- `dragon-studio-quick-whoosh-405448.mp3`
- `dragon-studio-cinematic-intro-463216.mp3` (optional cinematic layer)

Runtime never references the original download path.

## Intro Runtime Behavior
Implemented in `bit_life_survival/app/intro.py`, called from `bit_life_survival/app/main.py` before the base screen.

Timeline per guide:
- `0.0s - 0.5s`: black screen
- `0.5s - 2.0s`: `LOGOframe1` with subtle ~2% scale-in
- `2.0s`: hard cut to `LOGOframe2` + whoosh audio
- `2.0s - 2.3s`: impact shake + subtle flash + red glow spike
- `2.3s - 4.5s`: hold on `LOGOframe2` with mild pulse
- `4.5s - 6.0s`: fade to black

Skip behavior:
- Any key or mouse click skips immediately.

Failure handling:
- Missing assets/codec/audio errors are logged as warnings.
- App continues to the base screen instead of hard-failing.

## How To Replace Assets
1. Replace files in `bit_life_survival/assets/bbwg_intro/` using the same filenames.
2. Keep `LOGOframe1.png` and `LOGOframe2.png` the same dimensions and alignment.
3. Restart the app and verify intro playback.

## Disabling Intro
1. Persistent setting in save data:
   - In the Base screen, open `Settings` and toggle `skip_intro`.
2. Optional repo-level config override via `settings.json` at repo root:
   ```json
   {
     "skip_intro": true,
     "intro_use_cinematic_audio": false
   }
   ```
3. Environment override for one-off runs:
   - `BLS_SKIP_INTRO=1`
