from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, bytes):
        return f"<binary data: {len(value)} bytes>"
    return value


def display_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(json_safe(value), ensure_ascii=False)
    return str(value).replace("\x00", "")
