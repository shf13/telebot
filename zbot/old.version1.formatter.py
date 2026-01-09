from __future__ import annotations
import json
import os
from datetime import datetime, timezone


def load_latest(data_file: str) -> dict:
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Scrapy -O outputs a list of items
    if isinstance(data, list):
        if not data:
            return {}
        return data[0]
    return data


def format_message(payload: dict, data_file: str) -> str:
    if not payload or "prayers" not in payload:
        return "No data found yet."

    prayers = payload.get("prayers", {})
    date_str = payload.get("date", "")
    source_url = payload.get("source_url", "")

    # stale check via file mtime
    try:
        mtime = os.path.getmtime(data_file)
        age_hours = (datetime.now(timezone.utc).timestamp() - mtime) / 3600.0
    except OSError:
        age_hours = None

    lines = []
    title = f"Prayer times{(' — ' + date_str) if date_str else ''}"
    lines.append(title)
    lines.append("")

    # Keep the order as in the HTML if possible; otherwise dict order is usually fine (Python 3.7+ preserves insertion)
    for name, time_str in prayers.items():
        lines.append(f"{name}: {time_str}")

    if age_hours is not None and age_hours > 30:
        lines.append("")
        lines.append("(Warning: data may be stale.)")

    if source_url:
        lines.append("")
        lines.append(source_url)

    return "\n".join(lines)