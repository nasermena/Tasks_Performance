
# -*- coding: utf-8 -*-
"""
Task Sheet GUI for Google Sheets
- GUI flow: Start -> Pick Date -> Fill Task -> Post-Add actions
- Requires: pip install gspread google-auth tkcalendar
- Auth: Service Account JSON (share the target sheet with the service account email)
"""

import tkinter as tk
from tkinter import messagebox
from tkinter import scrolledtext
from tkcalendar import Calendar
from datetime import datetime, date

import gspread
from google.oauth2.service_account import Credentials

# ===================== CONFIG =====================
SERVICE_ACCOUNT_FILE = "C:\\Users\\Naser Rahal\\ServiceAccountKey\\service_account.json"
SHEET_ID = "19Juc5u43K4Xx3vU9yeyZVx5K-aRdOOm_c5etpfpcsWQ"
WORKSHEET_TITLE = "Sheet1442"   # غيّرها لاسم التبويب عندك



# Exact headers order in the Google Sheet
HEADERS = [
    "Task ID", "The prompt", "Justification", "Feedback", "rating", "submitted time",
    "Project", "Task duration (hour)", "Level", "Verdict",
    "Date", "Day", "Month"
]

# Month and day abbreviations (fixed English mapping to avoid locale issues)
MONTH_ABBR = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
DAY_ABBR   = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# ===================== Google Sheets Helper =====================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_worksheet():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(SHEET_ID)                 # ← فتح بالـID (أدق من open بالاسم)
    ws = sh.worksheet(WORKSHEET_TITLE)            # ← تبويب محدد بالاسم
    # ثبّت العناوين فقط إذا الصف 1 فارغ (لا تمسح بياناتك)
    header_row = ws.row_values(1)
    if not any(header_row):
        ws.insert_row(HEADERS, index=1)
    return ws


def append_task_row(row_values):
    ws = get_worksheet()
    ws.append_row(row_values, value_input_option="USER_ENTERED")


# ===================== GUI =====================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("إدارة تسجيل المهام - Google Sheets")
        self.geometry("850x720")
        self.resizable(False, False)

        # Shared state
        self.selected_date = None  # datetime.date
        self.selected_day_abbr = None
        self.selected_month_abbr = None

        self.last_defaults = {
            "Project": "",
            "Task duration (hour)": "",
            "Level": "",
            "Verdict": "",
        }

        # Frames
        self.frames = {}
        for F in (StartPage, DatePage, TaskFormPage, PostAddPage):
            frame = F(parent=self, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("StartPage")

    def show_frame(self, name):
        frame = self.frames[name]
        frame.tkraise()

    def set_date(self, dt: date):
        self.selected_date = dt
        # Compute day / month abbreviations using fixed tables
        weekday = dt.weekday()  # Mon=0..Sun=6
        self.selected_day_abbr = DAY_ABBR[weekday]
        self.selected_month_abbr = MONTH_ABBR[dt.month - 1]

    def reset_session(self):
        self.selected_date = None
        self.selected_day_abbr = None
        self.selected_month_abbr = None
        # Clear last defaults
        for k in self.last_defaults:
            self.last_defaults[k] = ""

class StartPage(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        lbl = tk.Label(self, text="تسجيل مهام اليوم على Google Sheets", font=("Arial", 20, "bold"))
        lbl.pack(pady=80)

        btn = tk.Button(self, text="ابدأ العمل", font=("Arial", 16, "bold"), width=20,
                        command=lambda: controller.show_frame("DatePage"))
        btn.pack(pady=10)

class DatePage(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        title = tk.Label(self, text="اختر التاريخ", font=("Arial", 18, "bold"))
        title.pack(pady=20)

        today = datetime.today()
        self.calendar = Calendar(self, selectmode="day", year=today.year, month=today.month, day=today.day, date_pattern="yyyy-mm-dd")
        self.calendar.pack(pady=10)

        self.info_lbl = tk.Label(self, text="لن يتم الانتقال حتى تختار تاريخًا.", font=("Arial", 12))
        self.info_lbl.pack(pady=8)

        buttons = tk.Frame(self)
        buttons.pack(pady=20)
        next_btn = tk.Button(buttons, text="التالي", width=16, command=self.on_next)
        next_btn.grid(row=0, column=1, padx=10)

    def on_next(self):
        sel = self.calendar.get_date()
        try:
            dt = datetime.strptime(sel, "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("خطأ", "يرجى اختيار تاريخ صالح من التقويم.")
            return

        self.controller.set_date(dt)
        self.controller.show_frame("TaskFormPage")

class TaskFormPage(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        header = tk.Label(self, text="إدخال تفاصيل المهمة", font=("Arial", 18, "bold"))
        header.grid(row=0, column=0, columnspan=4, pady=10)

        # Column layout (labels + entries)
        # Left column: Task ID, The prompt, Justification
        rowi = 1

        # Task ID (Entry)
        tk.Label(self, text="Task ID:", anchor="w").grid(row=rowi, column=0, sticky="w", padx=10, pady=6)
        self.var_task_id = tk.StringVar()
        self.entry_task_id = tk.Entry(self, textvariable=self.var_task_id, width=30)
        self.entry_task_id.grid(row=rowi, column=1, sticky="w", padx=10, pady=6)
        rowi += 1

        # The prompt (Text)
        tk.Label(self, text="The prompt:", anchor="w").grid(row=rowi, column=0, sticky="nw", padx=10, pady=6)
        self.txt_prompt = scrolledtext.ScrolledText(self, width=45, height=5)
        self.txt_prompt.grid(row=rowi, column=1, sticky="w", padx=10, pady=6)
        rowi += 1

        # Justification (Text)
        tk.Label(self, text="Justification:", anchor="w").grid(row=rowi, column=0, sticky="nw", padx=10, pady=6)
        self.txt_just = scrolledtext.ScrolledText(self, width=45, height=5)
        self.txt_just.grid(row=rowi, column=1, sticky="w", padx=10, pady=6)
        rowi += 1

        # Right column: Feedback, rating, submitted time
        rowr = 1

        tk.Label(self, text="Feedback:", anchor="w").grid(row=rowr, column=2, sticky="nw", padx=10, pady=6)
        self.txt_feedback = scrolledtext.ScrolledText(self, width=45, height=5)
        self.txt_feedback.grid(row=rowr, column=3, sticky="w", padx=10, pady=6)
        rowr += 1

        tk.Label(self, text="rating:", anchor="w").grid(row=rowr, column=2, sticky="w", padx=10, pady=6)
        self.var_rating = tk.StringVar()
        self.entry_rating = tk.Entry(self, textvariable=self.var_rating, width=30)
        self.entry_rating.grid(row=rowr, column=3, sticky="w", padx=10, pady=6)
        rowr += 1

        tk.Label(self, text="submitted time:", anchor="w").grid(row=rowr, column=2, sticky="w", padx=10, pady=6)
        self.var_submitted = tk.StringVar()
        self.entry_submitted = tk.Entry(self, textvariable=self.var_submitted, width=30)
        self.entry_submitted.grid(row=rowr, column=3, sticky="w", padx=10, pady=6)
        rowr += 1

        # Second row of both columns: Project, Task duration, Level, Verdict
        rowb = max(rowi, rowr)
        tk.Label(self, text="Project:", anchor="w").grid(row=rowb, column=0, sticky="w", padx=10, pady=6)
        self.var_project = tk.StringVar()
        self.entry_project = tk.Entry(self, textvariable=self.var_project, width=30)
        self.entry_project.grid(row=rowb, column=1, sticky="w", padx=10, pady=6)

        tk.Label(self, text="Task duration (hour):", anchor="w").grid(row=rowb, column=2, sticky="w", padx=10, pady=6)
        self.var_duration = tk.StringVar()
        self.entry_duration = tk.Entry(self, textvariable=self.var_duration, width=30)
        self.entry_duration.grid(row=rowb, column=3, sticky="w", padx=10, pady=6)

        rowb += 1
        tk.Label(self, text="Level:", anchor="w").grid(row=rowb, column=0, sticky="w", padx=10, pady=6)
        self.var_level = tk.StringVar()
        self.entry_level = tk.Entry(self, textvariable=self.var_level, width=30)
        self.entry_level.grid(row=rowb, column=1, sticky="w", padx=10, pady=6)

        tk.Label(self, text="Verdict:", anchor="w").grid(row=rowb, column=2, sticky="w", padx=10, pady=6)
        self.var_verdict = tk.StringVar()
        self.entry_verdict = tk.Entry(self, textvariable=self.var_verdict, width=30)
        self.entry_verdict.grid(row=rowb, column=3, sticky="w", padx=10, pady=6)

        # Buttons
        buttons = tk.Frame(self)
        buttons.grid(row=rowb+1, column=0, columnspan=4, pady=20)

        self.btn_add = tk.Button(buttons, text="إضافة المهمة", width=16, command=self.on_add_task, state="disabled")
        self.btn_add.grid(row=0, column=1, padx=10)

        # Validation: enable Add button only if Task ID present
        self.var_task_id.trace_add("write", self._update_add_state)

        # When entering this page, prefill project-related fields from last_defaults
        self.bind("<<ShowPage>>", self.on_show)

    def event_generate_show(self):
        # helper to trigger prefill when the frame is raised
        self.event_generate("<<ShowPage>>")

    def on_show(self, event=None):
        d = self.controller.last_defaults
        # Prefill
        self.var_project.set(d.get("Project",""))
        self.var_duration.set(d.get("Task duration (hour)",""))
        self.var_level.set(d.get("Level",""))
        self.var_verdict.set(d.get("Verdict",""))

    def _update_add_state(self, *args):
        if self.var_task_id.get().strip():
            self.btn_add.config(state="normal")
        else:
            self.btn_add.config(state="disabled")

    def on_add_task(self):
        if not self.controller.selected_date:
            messagebox.showerror("خطأ", "يرجى اختيار التاريخ أولاً.")
            return

        # Build the row in the exact order of HEADERS
        # Get big text fields
        prompt = self.txt_prompt.get("1.0", "end").strip()
        just   = self.txt_just.get("1.0", "end").strip()
        feed   = self.txt_feedback.get("1.0", "end").strip()

        row = [
            self.var_task_id.get().strip(),
            prompt,
            just,
            feed,
            self.var_rating.get().strip(),
            self.var_submitted.get().strip(),
            self.var_project.get().strip(),
            self.var_duration.get().strip(),
            self.var_level.get().strip(),
            self.var_verdict.get().strip(),
            self.controller.selected_date.strftime("%Y-%m-%d"),
            self.controller.selected_day_abbr,
            self.controller.selected_month_abbr
        ]

        try:
            append_task_row(row)
        except Exception as e:
            messagebox.showerror("فشل الإضافة", f"حدث خطأ أثناء الإضافة إلى Google Sheets:\n{e}")
            return

        # Save defaults for project-related fields
        self.controller.last_defaults["Project"] = self.var_project.get().strip()
        self.controller.last_defaults["Task duration (hour)"] = self.var_duration.get().strip()
        self.controller.last_defaults["Level"] = self.var_level.get().strip()
        self.controller.last_defaults["Verdict"] = self.var_verdict.get().strip()

        # Go to post-add page
        self.controller.show_frame("PostAddPage")
        # Clear only non-default fields for next time user returns here
        self.var_task_id.set("")
        self.txt_prompt.delete("1.0", "end")
        self.txt_just.delete("1.0", "end")
        self.txt_feedback.delete("1.0", "end")
        self.var_rating.set("")
        self.var_submitted.set("")

class PostAddPage(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        lbl = tk.Label(self, text="تمت إضافة المهمة بنجاح", font=("Arial", 18, "bold"))
        lbl.pack(pady=40)

        btns = tk.Frame(self)
        btns.pack(pady=10)

        btn_add_new = tk.Button(btns, text="إضافة مهمة جديدة", width=20, command=self.add_new_task)
        btn_finish  = tk.Button(btns, text="إنهاء العمل", width=20, command=self.finish_work)
        btn_add_new.grid(row=0, column=0, padx=10, pady=6)
        btn_finish.grid(row=0, column=1, padx=10, pady=6)

    def add_new_task(self):
        # Keep same date and prefilled defaults
        self.controller.show_frame("TaskFormPage")
        # Trigger prefill on TaskFormPage
        self.controller.frames["TaskFormPage"].event_generate_show()

    def finish_work(self):
        # إنهاء تشغيل الكود (إغلاق نافذة Tkinter)
        self.controller.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()
