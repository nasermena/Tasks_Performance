# Tasks Performance

A lightweight Tkinter desktop app for logging task work into Google Sheets.

The app guides you through a simple workflow:

1. Start the session.
2. Connect to a Google Sheets spreadsheet and worksheet.
3. Fill in task details while the built-in timer tracks duration.
4. Add more tasks or finish the session, with optional CSV export and daily-hours updates.

## Features

- Tkinter + ttk GUI with optional `sv-ttk` theme support.
- Google Sheets integration through `gspread` and a Google Service Account.
- Automatic header insertion when the selected worksheet is empty.
- Task timer that starts when the task form opens and can be reset.
- Task ID validation:
  - Must match `^[0-9a-f]{24}$`.
  - Duplicate IDs are blocked with a local cache and a final sheet-side check before append.
- Local and US time tracking:
  - Local timezone: `Asia/Amman`.
  - US timezone: `America/Los_Angeles`.
- OT defaulting based on the Los Angeles weekday, with rollover prompts when the LA day changes.
- Daily stats in the UI for tasks and hours submitted today.
- CSV export of the current worksheet.
- Optional external spreadsheet update on finish:
  - Updates the `Daily Hours` worksheet for today's total.
  - Adds a `WFH` row when today's total is greater than 7 hours, avoiding duplicates.
- Unit tests for config, persistence, and Google Sheets backend behavior.

## Repository Structure

```text
.
|-- cfg_store.py          # Local config persistence and credential path lookup
|-- config.py             # Shared constants, headers, regex, scopes, timezones
|-- sheets_backend.py     # Google Sheets access, CSV export, task ID cache, aggregations
|-- task_sheet_gui.py     # Tkinter application
|-- requirements.txt      # Runtime and test dependencies
|-- tests/                # Pytest suite with mocked Google Sheets calls
`-- README.md
```

## Requirements

- Python 3.10 or newer.
- A Google Cloud service account JSON key.
- Access to the target Google Sheet shared with the service account email.

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Optional GUI theme:

```powershell
python -m pip install sv-ttk
```

## Google Service Account Setup

1. Create a service account in Google Cloud.
2. Create and download a JSON key for that service account.
3. Share the target Google Sheet with the service account email using Editor access.

The app resolves credentials in this order:

1. `GOOGLE_APPLICATION_CREDENTIALS` environment variable.
2. Saved `service_account_file` path in `~/.task_sheet_gui.json`.
3. GUI file picker, if no valid saved path is found.

PowerShell example:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\path\to\service_account.json"
python task_sheet_gui.py
```

macOS/Linux example:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service_account.json"
python task_sheet_gui.py
```

## Run The App

```powershell
python task_sheet_gui.py
```

On the Google Sheets settings screen, enter:

- `Spreadsheet ID`
- `Worksheet title`

Successful values are saved in `~/.task_sheet_gui.json` for future sessions.

## Usage

1. Start the app.
2. Open the Google Sheets settings screen.
3. Enter the spreadsheet ID and worksheet title.
4. Confirm or adjust the OT value.
5. Fill in the task form:
   - Task ID
   - Prompt
   - Justification
   - Feedback
   - Rating
   - Project
   - Level
   - Verdict
6. Add the task once the button is enabled.
7. Add another task or finish the session.

When finishing, the app asks whether to export the current worksheet to CSV. It then attempts to update the configured external `Daily Hours` and `WFH` worksheets.

## Sheet Columns

Rows are appended in the order defined by `HEADERS` in `config.py`:

```text
Task ID, The prompt, Justification, Feedback, Rating,
Project, Task duration (hour), Level, Verdict,
Date, Day, Year, Month, Month (num),
Started Time, Submitted time,
Date (US), Day (US), Year (US), Month (US), Month (num_US),
Started Time (US), Submitted time (US), OT
```

If the target worksheet is empty, these headers are inserted automatically in row 1.

## Configuration

Local app settings are saved in:

```text
~/.task_sheet_gui.json
```

The file may contain:

```json
{
  "sheet_id": "your-spreadsheet-id",
  "worksheet": "your-worksheet-title",
  "service_account_file": "C:\\path\\to\\service_account.json"
}
```

External daily-hours integration is configured in `config.py`:

```python
EXTERNAL_SHEET_ID = "..."
DAILY_HOURS_SHEET = "Daily Hours"
WFH_SHEET = "WFH"
PERSON_FULLNAME_FOR_DAILY = "..."
PERSON_NAME_FOR_WFH = "..."
```

If you do not use the external daily-hours workflow, disable or remove the calls to `update_daily_hours_in_external_sheet()` and `upsert_wfh_row_if_needed()` in `PostAddPage.finish_work()`.

## Tests

Run the test suite:

```powershell
python -m pytest tests/ -v
```

The backend tests mock Google Sheets API calls, so they do not need real credentials or network access.

GitHub Actions runs the tests on Python 3.11 and 3.12.

## Troubleshooting

### Permission denied or worksheet not found

- Make sure the Google Sheet is shared with the service account email.
- Confirm that the spreadsheet ID is correct.
- Confirm that the worksheet title matches the tab name exactly.

### Add task button stays disabled

- The Task ID must be exactly 24 lowercase hex characters.
- The Task ID must not already exist in column A.
- Rating must be blank or numeric.

### Credentials are not picked up

- Check that `GOOGLE_APPLICATION_CREDENTIALS` points to an existing JSON file.
- Use the app button to clear the saved service-account path, then select the JSON file again.
- Delete or edit `~/.task_sheet_gui.json` if the saved path is stale.

### Time fields look unexpected

The app writes both Amman and Los Angeles timestamps. OT defaults are based on the Los Angeles date, while today's daily-hours total is computed using the Amman date.

## License

No license file is currently included.
