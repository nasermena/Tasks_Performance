# Tasks_Performance

A lightweight **Tkinter GUI** for logging daily tasks into **Google Sheets**, with automatic time tracking and optional updates to a separate “Daily Hours” / “WFH” spreadsheet.

The app is designed around a simple flow:

1. **Start**
2. **Google Sheets configuration**
3. **Fill task form + timer**
4. **Post-add actions / Finish (export CSV + update external sheets)**

---

## Features

- **GUI task entry** (Tkinter + ttk)
- **Google Sheets append** via `gspread` + Google Service Account credentials
- **Task timer** (auto starts when opening the form; can reset)
- **Validation**
  - `Task ID` must match: `^[0-9a-f]{24}$` (24 lowercase hex characters)
  - Prevents duplicate `Task ID`s (loads column A, caches IDs, plus a final server-side check before append)
- **Dual timezones**
  - Local: **Asia/Amman (JOR)**
  - US: **America/Los_Angeles (US)**
- **OT field** with automatic defaulting and day-rollover prompt logic (based on LA weekday)
- **Daily stats** shown in the UI (for Amman “today”):
  - number of tasks submitted today
  - total hours today
- **Export current worksheet to CSV** on finish
- **Optional external spreadsheet updates** on finish:
  - Update “Daily Hours” cell for today
  - Insert into “WFH” sheet if today’s hours > 7 (and prevent duplicates)

---

## Repository contents

- `task_sheet_gui.py` — main application script (GUI + Google Sheets integration)

---

## Requirements

- Python **3.10+** (uses `zoneinfo`)
- Packages:
  - `gspread`
  - `google-auth`
  - Optional theme: `sv-ttk`

Install:

```bash
pip install gspread google-auth
# optional:
pip install sv-ttk
```

---

## Google Service Account setup

1. Create a **Service Account** in Google Cloud.
2. Create and download its **JSON key**.
3. Share your target Google Sheet with the service account email (Editor access).

The app will look for credentials in this order:

1. Environment variable `GOOGLE_APPLICATION_CREDENTIALS` (preferred)
2. Saved path in `~/.task_sheet_gui.json`
3. If neither is available, it will prompt you to choose the JSON file via a file picker

### Recommended: set credentials via environment variable

**macOS/Linux**
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service_account.json"
python task_sheet_gui.py
```

**Windows (PowerShell)**
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\service_account.json"
python task_sheet_gui.py
```

---

## How to run

```bash
python task_sheet_gui.py
```

---

## Usage guide

### 1) Start page
Click **ابدأ العمل**.

### 2) Google Sheets settings
Enter:
- **Spreadsheet ID**
- **Worksheet title**

These values are saved for next time in:
- `~/.task_sheet_gui.json`

You can also:
- Clear saved service account file path
- Clear saved sheet settings

An **OT?** dropdown is shown on this page as well.

### 3) Task form
Fill in the task fields and click **إضافة المهمة** once enabled.

**Button enable rules**
- Task ID is valid and unique
- Rating is either blank or numeric

The app records both:
- Amman-local date/time fields
- Los Angeles date/time fields

### 4) Finish work
Click **إنهاء العمل**.
- The app asks if you want to export the current worksheet to a CSV.
- Then it attempts to update the external “Daily Hours” / “WFH” spreadsheet (if configured in the code).
- App closes.

---

## Data written to the sheet

The script maintains a `HEADERS` list that defines the exact order of columns appended. The row includes:

- Task ID
- Prompt / Justification / Feedback
- Rating, Project, Duration (hours), Level, Verdict
- Date/time fields for **Amman** and **Los Angeles**
- OT flag

If the worksheet is empty, the app inserts the headers automatically.

---

## Configuration notes (important)

Inside `task_sheet_gui.py` there are hard-coded values for an external spreadsheet update feature:

- `EXTERNAL_SHEET_ID`
- `DAILY_HOURS_SHEET`
- `WFH_SHEET`
- `PERSON_FULLNAME_FOR_DAILY`
- `PERSON_NAME_FOR_WFH`

If you don’t use this feature, you can keep them as-is, or remove/disable the external update calls in `PostAddPage.finish_work()`.

---

## Troubleshooting

### “Failed to open worksheet / permission denied”
- Ensure the **sheet is shared** with your service account email.
- Ensure Spreadsheet ID and Worksheet title are correct.

### The “Add task” button is disabled
- Confirm Task ID is exactly **24 hex characters** (0-9, a-f)
- Make sure the Task ID is **not already present** in column A

### Timezones look wrong
- The app uses:
  - `America/Los_Angeles`
  - `Asia/Amman`
- Ensure your Python version supports `zoneinfo` properly (Python 3.10+ recommended).

---

## License

No license file is currently included. If you want, add a `LICENSE` file (MIT/Apache-2.0/etc.) and update this section.