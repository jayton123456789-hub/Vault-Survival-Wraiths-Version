from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from bit_life_survival.core.loader import ContentValidationError, load_content


def test_missing_item_reference_in_loot_table_raises_clear_error(tmp_path: Path):
    source_content = Path(__file__).resolve().parents[1] / "content"
    test_content = tmp_path / "content"
    shutil.copytree(source_content, test_content)

    loottables_path = test_content / "loottables.json"
    loottables = json.loads(loottables_path.read_text(encoding="utf-8"))
    loottables[0]["entries"][0]["itemId"] = "missing_item_id"
    loottables_path.write_text(json.dumps(loottables, indent=2), encoding="utf-8")

    with pytest.raises(ContentValidationError, match="missing item 'missing_item_id'"):
        load_content(test_content)
