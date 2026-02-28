from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


DEFAULT_ZIP = Path(r"C:\Users\nickb\Downloads\vault_asset_pack_v1.zip")
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "bit_life_survival" / "assets" / "ui" / "buttons"
ZIP_PREFIX = "vault_asset_pack_v1/buttons/"


def import_buttons(zip_path: Path, output_dir: Path, force: bool = False) -> tuple[int, int]:
    extracted = 0
    skipped = 0
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        names = sorted(name for name in archive.namelist() if name.startswith(ZIP_PREFIX) and name.lower().endswith(".png"))
        for name in names:
            filename = Path(name).name
            target = output_dir / filename
            if target.exists() and not force:
                skipped += 1
                continue
            payload = archive.read(name)
            target.write_bytes(payload)
            extracted += 1
    return extracted, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Import vault asset pack button PNGs into project assets.")
    parser.add_argument("--zip", type=Path, default=DEFAULT_ZIP, help="Path to vault asset pack zip.")
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR, help="Output directory for imported buttons.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing button files.")
    args = parser.parse_args()

    if not args.zip.exists():
        raise SystemExit(f"Zip not found: {args.zip}")
    extracted, skipped = import_buttons(args.zip, args.out, force=args.force)
    print(f"Imported {extracted} button file(s), skipped {skipped}.")


if __name__ == "__main__":
    main()

