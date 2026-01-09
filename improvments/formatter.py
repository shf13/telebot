from __future__ import annotations

import json
from typing import Any


def load_latest(data_file: str) -> dict[str, Any]:
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        if not data:
            return {}
        first = data[0]
        return first if isinstance(first, dict) else {}

    return data if isinstance(data, dict) else {}