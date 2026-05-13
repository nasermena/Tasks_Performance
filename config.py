# -*- coding: utf-8 -*-
"""
Shared constants used by both the backend and the GUI.
No functions, no I/O — safe to import anywhere including test environments.
"""

import re
from zoneinfo import ZoneInfo

# ===================== Sheet structure =====================

# Column order sent to Google Sheets (must match the row built in on_add_task)
HEADERS = [
    "Task ID", "The prompt", "Justification", "Feedback", "Rating",
    "Project", "Task duration (hour)", "Level", "Verdict",
    "Date", "Day", "Year", "Month", "Month (num)",
    "Started Time", "Submitted time",
    "Date (US)", "Day (US)", "Year (US)", "Month (US)", "Month (num_US)",
    "Started Time (US)", "Submitted time (US)", "OT",
]

# Human-readable month / day abbreviations (locale-independent)
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_ABBR   = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Task ID pattern: exactly 24 lower-case hex characters
HEX24_RE = re.compile(r'^[0-9a-f]{24}$')

# ===================== Google Sheets API =====================

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# External (shared) spreadsheet IDs / worksheet names
EXTERNAL_SHEET_ID        = "1SEYwEPHgDDx6KVLKNZ4xbnuXMCVbCy7E9BgXvppkedA"
DAILY_HOURS_SHEET        = "Daily Hours"
WFH_SHEET                = "WFH"

PERSON_FULLNAME_FOR_DAILY = "Naser Basim Naser Rahhal"   # column A in Daily Hours
PERSON_NAME_FOR_WFH       = "Naser Rahhal"               # column A in WFH

# ===================== Timezones =====================

LA_TZ = ZoneInfo("America/Los_Angeles")
JO_TZ = ZoneInfo("Asia/Amman")
