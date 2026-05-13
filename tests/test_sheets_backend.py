"""
Tests for sheets_backend.py.

All Google Sheets API calls are mocked — no real network access required.
"""

import csv
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

import sheets_backend
from sheets_backend import (
    set_runtime_config,
    task_id_exists,
    register_task_id,
    _load_task_ids,
    compute_today_hours_from_current_sheet,
    update_daily_hours_in_external_sheet,
    upsert_wfh_row_if_needed,
    export_current_worksheet_to_csv,
    get_worksheet,
)
from config import JO_TZ, PERSON_FULLNAME_FOR_DAILY, PERSON_NAME_FOR_WFH, HEADERS


# ====================================================================
# Helpers
# ====================================================================

def _make_ws(rows=None):
    """Return a MagicMock gspread Worksheet with preset get_all_values()."""
    ws = MagicMock()
    ws.get_all_values.return_value = rows or []
    ws.spreadsheet.title = "My Spreadsheet"
    ws.title = "Sheet1"
    return ws


def _today_jo() -> str:
    return datetime.now(JO_TZ).strftime("%Y-%m-%d")


def _today_jo_slash() -> str:
    return datetime.now(JO_TZ).strftime("%Y/%m/%d")


# ====================================================================
# set_runtime_config
# ====================================================================

class TestSetRuntimeConfig:
    def test_sets_sheet_id_and_title(self):
        set_runtime_config("myid", "MySheet")
        assert sheets_backend.RUNTIME_SHEET_ID == "myid"
        assert sheets_backend.RUNTIME_WORKSHEET_TITLE == "MySheet"

    def test_clears_ws_cache(self):
        sheets_backend._WS = MagicMock()
        set_runtime_config("x", "y")
        assert sheets_backend._WS is None

    def test_clears_task_ids_cache(self):
        sheets_backend._TASK_IDS = {"abc123"}
        set_runtime_config("x", "y")
        assert sheets_backend._TASK_IDS is None


# ====================================================================
# get_worksheet
# ====================================================================

class TestGetWorksheet:
    def test_raises_when_config_not_set(self):
        with pytest.raises(RuntimeError, match="not set yet"):
            get_worksheet()

    def test_returns_cached_ws_without_reconnecting(self):
        mock_ws = _make_ws()
        sheets_backend._WS = mock_ws
        result = get_worksheet()
        assert result is mock_ws

    def test_raises_when_no_creds_and_no_prompter(self):
        set_runtime_config("sheet_id", "Tab1")
        sheets_backend._creds_file_prompter = None
        with patch("sheets_backend._get_service_account_path_from_env_or_cfg", return_value=None):
            with pytest.raises(RuntimeError, match="No service-account credentials"):
                get_worksheet()

    def test_raises_when_prompter_returns_empty(self):
        set_runtime_config("sheet_id", "Tab1")
        sheets_backend._creds_file_prompter = lambda: ""
        with patch("sheets_backend._get_service_account_path_from_env_or_cfg", return_value=None):
            with pytest.raises(RuntimeError):
                get_worksheet()

    def test_opens_worksheet_and_caches_it(self):
        set_runtime_config("sheet_id", "Tab1")
        mock_ws = _make_ws([["header"]])
        mock_ws.row_values.return_value = ["header"]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws

        with patch("sheets_backend._get_service_account_path_from_env_or_cfg", return_value="/fake/sa.json"):
            with patch("sheets_backend.Credentials.from_service_account_file"):
                with patch("sheets_backend.gspread.authorize") as mock_auth:
                    mock_auth.return_value.open_by_key.return_value = mock_sh
                    result = get_worksheet()

        assert result is mock_ws
        assert sheets_backend._WS is mock_ws

    def test_inserts_headers_when_sheet_is_empty(self):
        set_runtime_config("sheet_id", "Tab1")
        mock_ws = _make_ws()
        mock_ws.row_values.return_value = []       # empty sheet
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws

        with patch("sheets_backend._get_service_account_path_from_env_or_cfg", return_value="/fake/sa.json"):
            with patch("sheets_backend.Credentials.from_service_account_file"):
                with patch("sheets_backend.gspread.authorize") as mock_auth:
                    mock_auth.return_value.open_by_key.return_value = mock_sh
                    get_worksheet()

        mock_ws.insert_row.assert_called_once_with(HEADERS, index=1)

    def test_does_not_insert_headers_when_sheet_has_data(self):
        set_runtime_config("sheet_id", "Tab1")
        mock_ws = _make_ws()
        mock_ws.row_values.return_value = ["Task ID", "The prompt"]  # non-empty
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws

        with patch("sheets_backend._get_service_account_path_from_env_or_cfg", return_value="/fake/sa.json"):
            with patch("sheets_backend.Credentials.from_service_account_file"):
                with patch("sheets_backend.gspread.authorize") as mock_auth:
                    mock_auth.return_value.open_by_key.return_value = mock_sh
                    get_worksheet()

        mock_ws.insert_row.assert_not_called()


# ====================================================================
# Task-ID cache
# ====================================================================

class TestTaskIdCache:
    # ---- register_task_id ----

    def test_register_initialises_cache_if_none(self):
        sheets_backend._TASK_IDS = None
        register_task_id("aabbccddeeff001122334455")
        assert "aabbccddeeff001122334455" in sheets_backend._TASK_IDS

    def test_register_normalises_to_lowercase(self):
        sheets_backend._TASK_IDS = set()
        register_task_id("AABBCCDDEEFF001122334455")
        assert "aabbccddeeff001122334455" in sheets_backend._TASK_IDS

    def test_register_strips_whitespace(self):
        sheets_backend._TASK_IDS = set()
        register_task_id("  aabbccddeeff001122334455  ")
        assert "aabbccddeeff001122334455" in sheets_backend._TASK_IDS

    # ---- task_id_exists ----

    def test_returns_false_for_unknown_id(self):
        sheets_backend._TASK_IDS = set()
        assert not task_id_exists("000000000000000000000000")

    def test_returns_true_after_register(self):
        sheets_backend._TASK_IDS = set()
        tid = "aabbccddeeff001122334455"
        register_task_id(tid)
        assert task_id_exists(tid)

    def test_case_insensitive_lookup(self):
        sheets_backend._TASK_IDS = {"aabbccddeeff001122334455"}
        assert task_id_exists("AABBCCDDEEFF001122334455")

    def test_loads_from_sheet_when_cache_is_none(self):
        sheets_backend._TASK_IDS = None
        mock_ws = _make_ws()
        mock_ws.col_values.return_value = ["Task ID", "abc123abc123abc123abc123", "def456def456def456def456"]
        with patch("sheets_backend.get_worksheet", return_value=mock_ws):
            exists = task_id_exists("abc123abc123abc123abc123")
        assert exists is True

    # ---- _load_task_ids ----

    def test_load_task_ids_skips_header(self):
        mock_ws = _make_ws()
        mock_ws.col_values.return_value = ["Task ID", "aaa", "bbb", "ccc"]
        result = _load_task_ids(ws=mock_ws)
        assert "task id" not in result
        assert "aaa" in result
        assert "bbb" in result

    def test_load_task_ids_normalises_case(self):
        mock_ws = _make_ws()
        mock_ws.col_values.return_value = ["Task ID", "ABCDEF123456ABCDEF123456"]
        result = _load_task_ids(ws=mock_ws)
        assert "abcdef123456abcdef123456" in result

    def test_load_task_ids_ignores_empty_cells(self):
        mock_ws = _make_ws()
        mock_ws.col_values.return_value = ["Task ID", "", "   ", "realid"]
        result = _load_task_ids(ws=mock_ws)
        assert "" not in result
        assert "   " not in result
        assert "realid" in result


# ====================================================================
# compute_today_hours_from_current_sheet
# ====================================================================

class TestComputeTodayHours:
    def _header_row(self):
        return HEADERS[:]  # copy to avoid mutation

    def test_returns_zero_for_empty_sheet(self):
        mock_ws = _make_ws([])
        with patch("sheets_backend.get_worksheet", return_value=mock_ws):
            assert compute_today_hours_from_current_sheet() == 0.0

    def test_returns_zero_when_headers_only(self):
        mock_ws = _make_ws([self._header_row()])
        with patch("sheets_backend.get_worksheet", return_value=mock_ws):
            assert compute_today_hours_from_current_sheet() == 0.0

    def test_sums_todays_tasks(self):
        today = _today_jo()
        row_template = [""] * len(HEADERS)

        def make_row(duration, date_str):
            r = row_template[:]
            r[HEADERS.index("Task duration (hour)")] = str(duration)
            r[HEADERS.index("Date")] = date_str
            return r

        rows = [
            self._header_row(),
            make_row("2.5", today),
            make_row("1.0", today),
            make_row("1.5", "2024-01-01"),   # different day → excluded
        ]
        mock_ws = _make_ws(rows)
        with patch("sheets_backend.get_worksheet", return_value=mock_ws):
            result = compute_today_hours_from_current_sheet()
        assert abs(result - 3.5) < 1e-9

    def test_ignores_invalid_duration_values(self):
        today = _today_jo()
        row_template = [""] * len(HEADERS)

        def make_row(duration, date_str):
            r = row_template[:]
            r[HEADERS.index("Task duration (hour)")] = duration
            r[HEADERS.index("Date")] = date_str
            return r

        rows = [
            self._header_row(),
            make_row("not_a_number", today),
            make_row("2.0", today),
        ]
        mock_ws = _make_ws(rows)
        with patch("sheets_backend.get_worksheet", return_value=mock_ws):
            result = compute_today_hours_from_current_sheet()
        assert abs(result - 2.0) < 1e-9

    def test_returns_zero_when_missing_header_columns(self):
        mock_ws = _make_ws([["col_a", "col_b"]])
        with patch("sheets_backend.get_worksheet", return_value=mock_ws):
            result = compute_today_hours_from_current_sheet()
        assert result == 0.0

    def test_skips_short_rows(self):
        today = _today_jo()
        rows = [
            self._header_row(),
            ["task1"],          # row is too short → skipped
        ]
        mock_ws = _make_ws(rows)
        with patch("sheets_backend.get_worksheet", return_value=mock_ws):
            result = compute_today_hours_from_current_sheet()
        assert result == 0.0


# ====================================================================
# upsert_wfh_row_if_needed
# ====================================================================

class TestUpsertWfhRow:
    def test_returns_false_when_hours_at_threshold(self):
        assert upsert_wfh_row_if_needed(7.0) is False

    def test_returns_false_when_hours_below_threshold(self):
        assert upsert_wfh_row_if_needed(5.0) is False

    def test_returns_false_when_row_already_exists(self):
        today = _today_jo()
        mock_ws = MagicMock()
        mock_ws.get_all_values.return_value = [
            ["Name", "Date"],
            [PERSON_NAME_FOR_WFH, today],
        ]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws

        with patch("sheets_backend._open_external_spreadsheet", return_value=mock_sh):
            result = upsert_wfh_row_if_needed(8.0)

        assert result is False
        mock_ws.append_row.assert_not_called()

    def test_appends_row_when_hours_exceed_threshold_and_no_existing_row(self):
        today = _today_jo()
        mock_ws = MagicMock()
        mock_ws.get_all_values.return_value = [["Name", "Date"]]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws

        with patch("sheets_backend._open_external_spreadsheet", return_value=mock_sh):
            result = upsert_wfh_row_if_needed(8.0)

        assert result is True
        mock_ws.append_row.assert_called_once_with(
            [PERSON_NAME_FOR_WFH, today],
            value_input_option="USER_ENTERED",
        )

    def test_does_not_add_duplicate_on_same_day(self):
        today = _today_jo()
        mock_ws = MagicMock()
        mock_ws.get_all_values.return_value = [
            ["Name", "Date"],
            [PERSON_NAME_FOR_WFH, today],
            ["Someone Else", today],
        ]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws

        with patch("sheets_backend._open_external_spreadsheet", return_value=mock_sh):
            result = upsert_wfh_row_if_needed(9.0)

        assert result is False

    def test_adds_row_for_different_person_on_same_day(self):
        """A row for another person should not block adding our own row."""
        today = _today_jo()
        mock_ws = MagicMock()
        mock_ws.get_all_values.return_value = [
            ["Name", "Date"],
            ["Someone Else", today],
        ]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws

        with patch("sheets_backend._open_external_spreadsheet", return_value=mock_sh):
            result = upsert_wfh_row_if_needed(8.5)

        assert result is True


# ====================================================================
# update_daily_hours_in_external_sheet
# ====================================================================

class TestUpdateDailyHours:
    def _base_data(self, today_col=None, existing_val=""):
        today = today_col or _today_jo_slash()
        return [
            ["Name", today],
            [PERSON_FULLNAME_FOR_DAILY, existing_val],
        ]

    def test_updates_cell_when_value_changed(self):
        mock_ws = MagicMock()
        mock_ws.get_all_values.return_value = self._base_data(existing_val="3.00")
        mock_ws.cell.return_value.value = "3.00"
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws

        with patch("sheets_backend._open_external_spreadsheet", return_value=mock_sh):
            result = update_daily_hours_in_external_sheet(5.0)

        assert result is True
        mock_ws.update_cell.assert_called()

    def test_skips_write_when_value_unchanged(self):
        mock_ws = MagicMock()
        mock_ws.get_all_values.return_value = self._base_data(existing_val="5.00")
        mock_ws.cell.return_value.value = "5.00"
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws

        with patch("sheets_backend._open_external_spreadsheet", return_value=mock_sh):
            result = update_daily_hours_in_external_sheet(5.0)

        assert result is False
        # update_cell should NOT have been called for the data cell
        # (it may have been called for the header in previous steps, so we check the value)
        for c in mock_ws.update_cell.call_args_list:
            # Ensure we didn't write "5.00" again to the data cell
            args = c[0]
            if len(args) == 3:
                assert args[2] != "5.00"

    def test_writes_when_cell_was_empty(self):
        mock_ws = MagicMock()
        mock_ws.get_all_values.return_value = self._base_data(existing_val="")
        mock_ws.cell.return_value.value = ""
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws

        with patch("sheets_backend._open_external_spreadsheet", return_value=mock_sh):
            result = update_daily_hours_in_external_sheet(2.5)

        assert result is True

    def test_creates_new_column_when_date_not_found(self):
        """If today's date column does not exist, a new column header is written."""
        mock_ws = MagicMock()
        # Sheet has only a "Name" column — today's date is missing
        mock_ws.get_all_values.return_value = [
            ["Name"],
            [PERSON_FULLNAME_FOR_DAILY],
        ]
        mock_ws.cell.return_value.value = ""
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws

        with patch("sheets_backend._open_external_spreadsheet", return_value=mock_sh):
            update_daily_hours_in_external_sheet(3.0)

        # Should have called update_cell to write the date header
        calls_with_date = [
            c for c in mock_ws.update_cell.call_args_list
            if _today_jo_slash() in str(c)
        ]
        assert len(calls_with_date) >= 1

    def test_creates_new_person_row_when_not_found(self):
        """If the person row doesn't exist, it should be created."""
        mock_ws = MagicMock()
        today = _today_jo_slash()
        mock_ws.get_all_values.return_value = [
            ["Name", today],
            # person row is absent
        ]
        mock_ws.cell.return_value.value = ""
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws

        with patch("sheets_backend._open_external_spreadsheet", return_value=mock_sh):
            update_daily_hours_in_external_sheet(1.0)

        # update_cell should have been called with the person's full name
        calls_with_name = [
            c for c in mock_ws.update_cell.call_args_list
            if PERSON_FULLNAME_FOR_DAILY in str(c)
        ]
        assert len(calls_with_name) >= 1


# ====================================================================
# export_current_worksheet_to_csv
# ====================================================================

class TestExportWorksheetToCsv:
    def test_creates_csv_in_given_directory(self, tmp_path):
        mock_ws = _make_ws([
            ["Task ID", "Rating"],
            ["abc", "5"],
            ["def", "4"],
        ])
        with patch("sheets_backend.get_worksheet", return_value=mock_ws):
            out = export_current_worksheet_to_csv(dest_path=str(tmp_path))

        assert Path(out).exists()
        assert out.endswith(".csv")

    def test_csv_contains_correct_data(self, tmp_path):
        rows = [
            ["Task ID", "Rating"],
            ["abc123", "5"],
        ]
        mock_ws = _make_ws(rows)
        with patch("sheets_backend.get_worksheet", return_value=mock_ws):
            out = export_current_worksheet_to_csv(dest_path=str(tmp_path))

        with open(out, encoding="utf-8-sig", newline="") as f:
            reader = list(csv.reader(f))
        assert reader[0] == ["Task ID", "Rating"]
        assert reader[1] == ["abc123", "5"]

    def test_filename_uses_spreadsheet_and_worksheet_titles(self, tmp_path):
        mock_ws = _make_ws([["col"]])
        mock_ws.spreadsheet.title = "My Tasks"
        mock_ws.title = "June 2026"
        with patch("sheets_backend.get_worksheet", return_value=mock_ws):
            out = export_current_worksheet_to_csv(dest_path=str(tmp_path))

        assert "My Tasks" in Path(out).name
        assert "June 2026" in Path(out).name

    def test_sanitises_illegal_chars_in_filename(self, tmp_path):
        mock_ws = _make_ws([["col"]])
        mock_ws.spreadsheet.title = 'Bad:Name/Here"OK'
        mock_ws.title = "Sheet*1"
        with patch("sheets_backend.get_worksheet", return_value=mock_ws):
            out = export_current_worksheet_to_csv(dest_path=str(tmp_path))

        filename = Path(out).name
        for ch in r'\/:*?"<>|':
            assert ch not in filename

    def test_accepts_explicit_file_path(self, tmp_path):
        target = tmp_path / "explicit_output.csv"
        mock_ws = _make_ws([["h1"], ["v1"]])
        with patch("sheets_backend.get_worksheet", return_value=mock_ws):
            out = export_current_worksheet_to_csv(dest_path=str(target))

        assert Path(out) == target
        assert target.exists()

    def test_returns_absolute_path_string(self, tmp_path):
        mock_ws = _make_ws([["col"]])
        with patch("sheets_backend.get_worksheet", return_value=mock_ws):
            out = export_current_worksheet_to_csv(dest_path=str(tmp_path))

        assert os.path.isabs(out)
