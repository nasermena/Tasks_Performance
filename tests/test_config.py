"""Tests for config.py — constants that the whole app depends on."""

import re
import pytest
from config import (
    HEADERS, MONTH_ABBR, DAY_ABBR, HEX24_RE,
    SCOPES, LA_TZ, JO_TZ,
    DAILY_HOURS_SHEET, WFH_SHEET,
    PERSON_FULLNAME_FOR_DAILY, PERSON_NAME_FOR_WFH,
)


# ------------------------------------------------------------------ HEADERS --

class TestHeaders:
    def test_header_count(self):
        """HEADERS must have exactly 24 columns (matches the row built in the GUI)."""
        assert len(HEADERS) == 24

    def test_no_duplicate_headers(self):
        assert len(HEADERS) == len(set(HEADERS))

    def test_required_columns_present(self):
        required = [
            "Task ID", "The prompt", "Justification", "Feedback",
            "Rating", "Project", "Task duration (hour)", "Level", "Verdict",
            "Date", "OT",
        ]
        for col in required:
            assert col in HEADERS, f"Missing required column: {col}"

    def test_task_id_is_first_column(self):
        assert HEADERS[0] == "Task ID"

    def test_ot_is_last_column(self):
        assert HEADERS[-1] == "OT"


# ---------------------------------------------------------- MONTH / DAY ABBR --

class TestAbbreviations:
    def test_month_abbr_length(self):
        assert len(MONTH_ABBR) == 12

    def test_day_abbr_length(self):
        assert len(DAY_ABBR) == 7

    def test_month_abbr_values(self):
        assert MONTH_ABBR[0] == "Jan"
        assert MONTH_ABBR[11] == "Dec"

    def test_day_abbr_starts_monday(self):
        # Python weekday() is Mon=0 … Sun=6
        assert DAY_ABBR[0] == "Mon"
        assert DAY_ABBR[6] == "Sun"

    def test_all_abbr_are_three_chars(self):
        for abbr in MONTH_ABBR + DAY_ABBR:
            assert len(abbr) == 3, f"Unexpected abbreviation length: {abbr!r}"


# --------------------------------------------------------------- HEX24_RE ---

class TestHex24Re:
    VALID = [
        "a" * 24,
        "0" * 24,
        "f" * 24,
        "1234567890abcdef12345678",
        "deadbeefdeadbeefdeadbeef",
    ]
    INVALID = [
        "",                          # empty
        "a" * 23,                    # too short
        "a" * 25,                    # too long
        "A" * 24,                    # uppercase not allowed
        "z" * 24,                    # non-hex letter
        "1234567890abcdef1234567g",  # trailing non-hex char
        "1234567890abcdef123456 78", # space inside
    ]

    @pytest.mark.parametrize("tid", VALID)
    def test_valid_task_ids(self, tid):
        assert HEX24_RE.match(tid), f"Expected match for: {tid!r}"

    @pytest.mark.parametrize("tid", INVALID)
    def test_invalid_task_ids(self, tid):
        assert not HEX24_RE.match(tid), f"Expected no match for: {tid!r}"


# ------------------------------------------------------------ GOOGLE SCOPES --

class TestScopes:
    def test_scopes_is_list(self):
        assert isinstance(SCOPES, list)

    def test_spreadsheets_scope_present(self):
        assert any("spreadsheets" in s for s in SCOPES)


# --------------------------------------------------------------- TIMEZONES --

class TestTimezones:
    def test_la_tz_key(self):
        assert LA_TZ.key == "America/Los_Angeles"

    def test_jo_tz_key(self):
        assert JO_TZ.key == "Asia/Amman"

    def test_la_and_jo_are_different(self):
        assert LA_TZ != JO_TZ


# ------------------------------------------------------------- SHEET NAMES --

class TestSheetNames:
    def test_daily_hours_sheet_name(self):
        assert DAILY_HOURS_SHEET == "Daily Hours"

    def test_wfh_sheet_name(self):
        assert WFH_SHEET == "WFH"

    def test_person_names_are_non_empty(self):
        assert PERSON_FULLNAME_FOR_DAILY
        assert PERSON_NAME_FOR_WFH
