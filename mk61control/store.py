"""Local storage for things the keyboard cannot report back (keymaps, macros)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .layout import DEFAULT_FN, DEFAULT_NORMAL


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(Path.home(), ".config")
    d = Path(base) / "mk61-control"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path() -> Path:
    return config_dir() / "profiles.json"


def default_profile() -> dict:
    return {"normal": list(DEFAULT_NORMAL), "fn": list(DEFAULT_FN), "macros": {},
            "arrow_swap": False, "win_lock": False}


def load() -> dict:
    data = {}
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    for p in ("1", "2", "3", "4"):
        prof = data.get(p) or {}
        base = default_profile()
        base.update(prof)
        data[p] = base
    return data


def save(data: dict):
    _path().write_text(json.dumps(data, indent=1), encoding="utf-8")
