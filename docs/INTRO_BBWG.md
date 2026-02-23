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

No runtime file access uses the original downloads folder.

## Intro Runtime Behavior
Implemented in `bit_life_survival/app/intro.py`, called at startup from `bit_life_survival/app/main.py` before the main menu shell.

Timeline implemented per guide:
- `0.0s - 0.5s`: black screen
- `0.5s - 2.0s`: `LOGOframe1` with subtle ~2% scale-in
- `2.0s`: hard cut to `LOGOframe2` + whoosh audio (no crossfade/slide)
- `2.0s - 2.3s`: small shake, subtle flash, red glow spike
- `2.3s - 4.5s`: aggressive hold on `LOGOframe2` with subtle pulse/breathing
- `4.5s - 6.0s`: smooth fade to black

Skip support:
- Any key press or mouse click skips immediately.

## Replacing Intro Assets
1. Replace files in `bit_life_survival/assets/bbwg_intro/` using the same filenames.
2. Keep `LOGOframe1.png` and `LOGOframe2.png` identical resolution and center/pivot alignment.
3. Restart app; intro loader validates required files and frame dimension match.

## Disable Intro
Two supported switches:
1. Environment variable:
   - `BLS_DISABLE_INTRO=1`
2. `settings.json` at repo root:
   ```json
   {
     "disable_intro": true
   }
   ```

Optional cinematic layer can be toggled via:
```json
{
  "intro_use_cinematic_audio": false
}
```
