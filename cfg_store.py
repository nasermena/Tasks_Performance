# -*- coding: utf-8 -*-
"""
Config persistence: read / write the ~/.task_sheet_gui.json settings file,
and resolve the Google service-account credentials path.

No tkinter, no gspread — safe to import in test environments.
"""

import json
import os
from pathlib import Path

_CFG_FILE = Path.home() / ".task_sheet_gui.json"


def _load_cfg() -> dict:
    """Return the saved config dict, or {} if the file is missing/corrupt."""
    try:
        if _CFG_FILE.exists():
            return json.loads(_CFG_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_cfg(d: dict) -> None:
    """Write *d* to the config file (silently ignores I/O errors)."""
    try:
        _CFG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CFG_FILE.write_text(
            json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _get_service_account_path_from_env_or_cfg() -> str | None:
    """
    Return a usable service-account file path, checking in order:
    1. GOOGLE_APPLICATION_CREDENTIALS environment variable
    2. ``service_account_file`` key in the saved config file
    Returns None if nothing is found or the path does not exist.
    """
    env_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path and os.path.exists(env_path):
        return env_path

    cfg = _load_cfg()
    cfg_path = cfg.get("service_account_file")
    if cfg_path and os.path.exists(cfg_path):
        return cfg_path

    return None
