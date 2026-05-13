# -*- coding: utf-8 -*-
"""
Google Sheets back-end: all API calls and data-layer logic.

Deliberately has NO tkinter imports so it can be imported and tested
in headless environments.  When a credentials file must be selected
interactively, the GUI sets `_creds_file_prompter` to a callable that
opens a file-picker dialog and returns the chosen path (or "").
"""

import csv
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import gspread
from google.oauth2.service_account import Credentials

from config import (
    HEADERS, SCOPES,
    EXTERNAL_SHEET_ID, DAILY_HOURS_SHEET, WFH_SHEET,
    PERSON_FULLNAME_FOR_DAILY, PERSON_NAME_FOR_WFH,
    JO_TZ,
)
from cfg_store import _load_cfg, _save_cfg, _get_service_account_path_from_env_or_cfg

# ===================== Runtime state =====================

RUNTIME_SHEET_ID: Optional[str] = None
RUNTIME_WORKSHEET_TITLE: Optional[str] = None

_WS = None          # cached gspread Worksheet
_TASK_IDS = None    # cached set of lower-case task IDs

# Injected by the GUI so the backend never imports tkinter directly.
# Signature: () -> str   (returns chosen path, or "" if cancelled)
_creds_file_prompter: Optional[Callable[[], str]] = None


# ===================== Public config helper =====================

def set_runtime_config(sheet_id: str, worksheet_title: str) -> None:
    """
    Store the active sheet coordinates and clear all caches.
    Call this whenever the user changes the target sheet.
    """
    global RUNTIME_SHEET_ID, RUNTIME_WORKSHEET_TITLE, _WS, _TASK_IDS
    RUNTIME_SHEET_ID = sheet_id
    RUNTIME_WORKSHEET_TITLE = worksheet_title
    _WS = None
    _TASK_IDS = None


# ===================== Internal helpers =====================

def _resolve_creds_path() -> str:
    """
    Return a valid service-account file path or raise RuntimeError.
    Priority: env var → saved config → prompter callback.
    """
    creds_path = _get_service_account_path_from_env_or_cfg()
    if not creds_path:
        if _creds_file_prompter is None:
            raise RuntimeError(
                "No service-account credentials found. "
                "Set GOOGLE_APPLICATION_CREDENTIALS or configure the app."
            )
        creds_path = _creds_file_prompter()
        if not creds_path:
            raise RuntimeError("لم يتم اختيار ملف الخدمة (Service Account).")
    return creds_path


# ===================== Worksheet access =====================

def get_worksheet():
    """
    Return the active gspread Worksheet (opens connection on first call).
    Raises RuntimeError when sheet configuration is missing.
    """
    global _WS
    if _WS is not None:
        return _WS
    if not RUNTIME_SHEET_ID or not RUNTIME_WORKSHEET_TITLE:
        raise RuntimeError("Sheet ID/Worksheet title are not set yet.")

    creds_path = _resolve_creds_path()
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(RUNTIME_SHEET_ID)
    ws = sh.worksheet(RUNTIME_WORKSHEET_TITLE)

    # Write headers if the sheet is blank
    if not any(ws.row_values(1)):
        ws.insert_row(HEADERS, index=1)

    # Persist credentials path for future sessions
    try:
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            cfg = _load_cfg()
            cfg["service_account_file"] = creds_path
            _save_cfg(cfg)
    except Exception:
        pass

    _WS = ws
    return ws


def append_task_row(row_values: list) -> object:
    """Append one data row using USER_ENTERED input (honours sheet formulas)."""
    ws = get_worksheet()
    ws.append_row(row_values, value_input_option="USER_ENTERED")
    return ws


def export_current_worksheet_to_csv(dest_path=None) -> str:
    """
    Download the active worksheet and save it as a UTF-8 BOM CSV file.

    The filename is ``"<Spreadsheet> - <Worksheet>.csv"``.  Pass *dest_path*
    as a directory to override the default location (same folder as this file).
    Returns the absolute path of the written file.
    """
    ws = get_worksheet()
    rows = ws.get_all_values()

    def _safe(name: str) -> str:
        return re.sub(r'[\\/:"*?<>|]+', "_", name).strip()

    filename = f"{_safe(ws.spreadsheet.title)} - {_safe(ws.title)}.csv"

    script_dir = Path(__file__).resolve().parent
    if dest_path is None:
        out_path = script_dir / filename
    else:
        p = Path(dest_path)
        out_path = (p / filename) if p.is_dir() else p

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(rows)

    return str(out_path)


# ===================== Task-ID cache =====================

def _load_task_ids(ws=None) -> set:
    """Load all Task IDs from column A (skipping the header) into the cache."""
    global _TASK_IDS
    if ws is None:
        ws = get_worksheet()
    vals = ws.col_values(1)[1:]
    _TASK_IDS = {v.strip().lower() for v in vals if v and v.strip()}
    return _TASK_IDS


def task_id_exists(tid: str) -> bool:
    """Return True if *tid* already exists in the sheet (uses local cache)."""
    global _TASK_IDS
    if _TASK_IDS is None:
        _load_task_ids()
    return tid.strip().lower() in _TASK_IDS


def register_task_id(tid: str) -> None:
    """Update the local cache after a successful append (avoids a re-fetch)."""
    global _TASK_IDS
    if _TASK_IDS is None:
        _TASK_IDS = set()
    _TASK_IDS.add(tid.strip().lower())


# ===================== Aggregations =====================

def compute_today_hours_from_current_sheet() -> float:
    """
    Sum 'Task duration (hour)' for all rows whose 'Date' column equals
    today's date in the Amman timezone.
    """
    ws = get_worksheet()
    values = ws.get_all_values()
    if not values:
        return 0.0

    headers = values[0]
    try:
        idx_duration = headers.index("Task duration (hour)")
        idx_date_loc = headers.index("Date")
    except ValueError:
        return 0.0

    today_local = datetime.now(JO_TZ).strftime("%Y-%m-%d")
    total = 0.0
    for row in values[1:]:
        if len(row) <= max(idx_duration, idx_date_loc):
            continue
        if row[idx_date_loc].strip() == today_local:
            try:
                total += float((row[idx_duration] or "0").strip() or 0)
            except Exception:
                pass
    return total


# ===================== External sheet =====================

def _open_external_spreadsheet():
    """Open the shared external spreadsheet using service-account credentials."""
    creds_path = _resolve_creds_path()
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    gc = gspread.authorize(creds)
    try:
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            cfg = _load_cfg()
            cfg["service_account_file"] = creds_path
            _save_cfg(cfg)
    except Exception:
        pass
    return gc.open_by_key(EXTERNAL_SHEET_ID)


def update_daily_hours_in_external_sheet(total_hours_today: float) -> bool:
    """
    Write *total_hours_today* into today's cell in the Daily Hours worksheet.

    Skips the write if the stored value is already equal (within 1e-6).
    Returns True when the cell was actually updated, False otherwise.
    """
    sh = _open_external_spreadsheet()
    ws = sh.worksheet(DAILY_HOURS_SHEET)

    data = ws.get_all_values()
    if not data:
        ws.append_row(["Name"])
        data = ws.get_all_values()

    headers = data[0] if data else ["Name"]
    today_col_title = datetime.now(JO_TZ).strftime("%Y/%m/%d")

    # Find or create the column for today's date
    try:
        col_idx = headers.index(today_col_title) + 1  # 1-based
    except ValueError:
        ws.update_cell(1, len(headers) + 1, today_col_title)
        col_idx = len(headers) + 1
        headers.append(today_col_title)

    # Find or create the row for this person
    target_row_idx = None
    for r, row in enumerate(data[1:], start=2):
        if row and row[0].strip() == PERSON_FULLNAME_FOR_DAILY:
            target_row_idx = r
            break
    if target_row_idx is None:
        target_row_idx = len(data) + 1
        ws.update_cell(target_row_idx, 1, PERSON_FULLNAME_FOR_DAILY)

    current_val = ws.cell(target_row_idx, col_idx).value or ""
    try:
        current_float = float(current_val)
    except Exception:
        current_float = None

    new_val = round(float(total_hours_today), 2)
    if current_float is None or abs(current_float - new_val) > 1e-6:
        ws.update_cell(target_row_idx, col_idx, f"{new_val:.2f}")
        return True
    return False


def upsert_wfh_row_if_needed(total_hours_today: float) -> bool:
    """
    Append a WFH row [name, date] for today if *total_hours_today* > 7
    and the row does not already exist.  Returns True when a row was added.
    """
    if total_hours_today <= 7.0:
        return False

    sh = _open_external_spreadsheet()
    ws = sh.worksheet(WFH_SHEET)

    values = ws.get_all_values()
    today_iso = datetime.now(JO_TZ).strftime("%Y-%m-%d")

    for row in values[1:]:
        name = row[0].strip() if len(row) > 0 else ""
        d    = row[1].strip() if len(row) > 1 else ""
        if name == PERSON_NAME_FOR_WFH and d == today_iso:
            return False  # already logged

    ws.append_row([PERSON_NAME_FOR_WFH, today_iso], value_input_option="USER_ENTERED")
    return True
