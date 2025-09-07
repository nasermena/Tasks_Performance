# -*- coding: utf-8 -*-
"""
Task Sheet GUI for Google Sheets (TTK Styled UI)
- Visual refresh: ttk theme, top bar, label frames (cards), status bar
- Flow: Start -> Pick Date -> Fill Task -> Post-Add actions
- Requires: pip install gspread google-auth tkcalendar
- Auth: Service Account JSON (share the target sheet with the service account email)
"""
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
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
    return ws


# ===================== GUI =====================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("إدارة تسجيل المهام - Google Sheets")
        self.geometry("980x780")
        self.resizable(False, False)

        # --- Theme & Style ---
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except:
            pass

        BASE_FONT = ("Segoe UI", 11)
        TITLE_FONT = ("Segoe UI", 18, "bold")

        style.configure(".", font=BASE_FONT)
        style.configure("TButton", padding=(10, 6))
        style.configure("TLabel", padding=(2, 2))
        style.configure("Header.TLabel", font=TITLE_FONT)
        style.configure("Card.TLabelframe", padding=12)
        style.configure("Card.TLabelframe.Label", font=("Segoe UI", 12, "bold"))

        # Shared state
        self.selected_date = None
        self.selected_day_abbr = None
        self.selected_month_abbr = None

        self.last_defaults = {
            "Project": "",
            "Task duration (hour)": "",
            "Level": "",
            "Verdict": "",
        }

        # Top bar
        topbar = tk.Frame(self, bg="#0ea5e9", height=52)
        topbar.grid(row=0, column=0, sticky="we")
        top_title = tk.Label(topbar, text="تسجيل مهام اليوم على Google Sheets",
                             bg="#0ea5e9", fg="white", font=("Segoe UI", 16, "bold"))
        top_title.pack(side="right", padx=16)

        # Container for pages
        container = tk.Frame(self)
        container.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Frames (pages)
        self.frames = {}
        for F in (StartPage, DatePage, TaskFormPage, PostAddPage):
            frame = F(parent=container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Status bar
        self.status = tk.StringVar(value="Ready")
        status_lbl = ttk.Label(self, textvariable=self.status, anchor="w")
        status_lbl.grid(row=2, column=0, sticky="we", padx=8, pady=(0,8))

        self.show_frame("StartPage")

    def show_frame(self, name):
        frame = self.frames[name]
        frame.tkraise()

    def set_date(self, dt: date):
        self.selected_date = dt
        weekday = dt.weekday()  # Mon=0..Sun=6
        self.selected_day_abbr = DAY_ABBR[weekday]
        self.selected_month_abbr = MONTH_ABBR[dt.month - 1]

    def reset_session(self):
        self.selected_date = None
        self.selected_day_abbr = None
        self.selected_month_abbr = None
        for k in self.last_defaults:
            self.last_defaults[k] = ""

class StartPage(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        lbl = ttk.Label(self, text="ابدأ العمل", style="Header.TLabel")
        lbl.pack(pady=40)

        btn = ttk.Button(self, text="ابدأ العمل", width=24,
                         command=lambda: controller.show_frame("DatePage"))
        btn.pack(pady=6)

class DatePage(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        title = ttk.Label(self, text="اختر التاريخ", style="Header.TLabel")
        title.pack(pady=16)

        today = datetime.today()
        self.calendar = Calendar(self, selectmode="day", year=today.year, month=today.month, day=today.day, date_pattern="yyyy-mm-dd")
        self.calendar.pack(pady=10)

        self.info_lbl = ttk.Label(self, text="لن يتم الانتقال حتى تختار تاريخًا.")
        self.info_lbl.pack(pady=8)

        controls = ttk.Frame(self)
        controls.pack(pady=16)

        next_btn = ttk.Button(controls, text="التالي", command=self.on_next)
        next_btn.grid(row=0, column=1, padx=8)

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

        header = ttk.Label(self, text="إدخال تفاصيل المهمة", style="Header.TLabel")
        header.grid(row=0, column=0, columnspan=4, pady=(8, 12), sticky="e")

        # Cards
        left_card  = ttk.Labelframe(self, text="تفاصيل المهمة", style="Card.TLabelframe")
        right_card = ttk.Labelframe(self, text="التقييم والتوقيت", style="Card.TLabelframe")
        meta_card  = ttk.Labelframe(self, text="بيانات المشروع", style="Card.TLabelframe")

        left_card.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8, pady=6)
        right_card.grid(row=1, column=2, columnspan=2, sticky="nsew", padx=8, pady=6)
        meta_card.grid(row=2, column=0, columnspan=4, sticky="nsew", padx=8, pady=6)

        for c in (0,1,2,3):
            self.grid_columnconfigure(c, weight=1)

        # --- left_card ---
        ttk.Label(left_card, text="Task ID:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        self.var_task_id = tk.StringVar()
        self.entry_task_id = ttk.Entry(left_card, textvariable=self.var_task_id, width=36, justify="right")
        self.entry_task_id.grid(row=0, column=1, sticky="we", padx=6, pady=6)

        ttk.Label(left_card, text="The prompt:").grid(row=1, column=0, sticky="ne", padx=6, pady=6)
        self.txt_prompt = scrolledtext.ScrolledText(left_card, width=44, height=5)
        self.txt_prompt.grid(row=1, column=1, sticky="we", padx=6, pady=6)

        ttk.Label(left_card, text="Justification:").grid(row=2, column=0, sticky="ne", padx=6, pady=6)
        self.txt_just = scrolledtext.ScrolledText(left_card, width=44, height=5)
        self.txt_just.grid(row=2, column=1, sticky="we", padx=6, pady=6)

        for c in (0,1):
            left_card.grid_columnconfigure(c, weight=1)

        # --- right_card ---
        ttk.Label(right_card, text="Feedback:").grid(row=0, column=0, sticky="ne", padx=6, pady=6)
        self.txt_feedback = scrolledtext.ScrolledText(right_card, width=44, height=5)
        self.txt_feedback.grid(row=0, column=1, sticky="we", padx=6, pady=6)

        ttk.Label(right_card, text="rating:").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        self.var_rating = tk.StringVar()
        self.entry_rating = ttk.Entry(right_card, textvariable=self.var_rating, width=36, justify="right")
        self.entry_rating.grid(row=1, column=1, sticky="we", padx=6, pady=6)

        ttk.Label(right_card, text="submitted time:").grid(row=2, column=0, sticky="e", padx=6, pady=6)
        self.var_submitted = tk.StringVar()
        self.entry_submitted = ttk.Entry(right_card, textvariable=self.var_submitted, width=36, justify="right")
        self.entry_submitted.grid(row=2, column=1, sticky="we", padx=6, pady=6)

        for c in (0,1):
            right_card.grid_columnconfigure(c, weight=1)

        # --- meta_card ---
        ttk.Label(meta_card, text="Project:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        self.var_project = tk.StringVar()
        self.entry_project = ttk.Entry(meta_card, textvariable=self.var_project, width=36, justify="right")
        self.entry_project.grid(row=0, column=1, sticky="we", padx=6, pady=6)

        ttk.Label(meta_card, text="Task duration (hour):").grid(row=0, column=2, sticky="e", padx=6, pady=6)
        self.var_duration = tk.StringVar()
        self.entry_duration = ttk.Entry(meta_card, textvariable=self.var_duration, width=36, justify="right")
        self.entry_duration.grid(row=0, column=3, sticky="we", padx=6, pady=6)

        ttk.Label(meta_card, text="Level:").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        self.var_level = tk.StringVar()
        self.entry_level = ttk.Entry(meta_card, textvariable=self.var_level, width=36, justify="right")
        self.entry_level.grid(row=1, column=1, sticky="we", padx=6, pady=6)

        ttk.Label(meta_card, text="Verdict:").grid(row=1, column=2, sticky="e", padx=6, pady=6)
        self.var_verdict = tk.StringVar()
        self.entry_verdict = ttk.Entry(meta_card, textvariable=self.var_verdict, width=36, justify="right")
        self.entry_verdict.grid(row=1, column=3, sticky="we", padx=6, pady=6)

        for c in (0,1,2,3):
            meta_card.grid_columnconfigure(c, weight=1)

        # Buttons
        buttons = ttk.Frame(self)
        buttons.grid(row=3, column=0, columnspan=4, pady=12)

        self.btn_add  = ttk.Button(buttons, text="إضافة المهمة", command=self.on_add_task, state="disabled")
        self.btn_add.grid(row=0, column=1, padx=8)

        # Validation: enable Add button only if Task ID present
        self.var_task_id.trace_add("write", self._update_add_state)

        # When entering this page, prefill project-related fields from last_defaults
        self.bind("<<ShowPage>>", self.on_show)

    def event_generate_show(self):
        self.event_generate("<<ShowPage>>")

    def on_show(self, event=None):
        d = self.controller.last_defaults
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
            ws = append_task_row(row)
        except Exception as e:
            messagebox.showerror("فشل الإضافة", f"حدث خطأ أثناء الإضافة إلى Google Sheets:\n{e}")
            return

        # Save defaults
        self.controller.last_defaults["Project"] = self.var_project.get().strip()
        self.controller.last_defaults["Task duration (hour)"] = self.var_duration.get().strip()
        self.controller.last_defaults["Level"] = self.var_level.get().strip()
        self.controller.last_defaults["Verdict"] = self.var_verdict.get().strip()

        # Status
        self.controller.status.set(f"✓ Added to: {ws.spreadsheet.url} / {ws.title}")

        # Go to post-add page
        self.controller.show_frame("PostAddPage")

        # Clear non-default fields
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

        lbl = ttk.Label(self, text="تمت إضافة المهمة بنجاح", style="Header.TLabel")
        lbl.pack(pady=24)

        btns = ttk.Frame(self)
        btns.pack(pady=6)

        btn_add_new = ttk.Button(btns, text="إضافة مهمة جديدة", width=24, command=self.add_new_task)
        btn_finish  = ttk.Button(btns, text="إنهاء العمل", width=24, command=self.finish_work)
        btn_add_new.grid(row=0, column=0, padx=8, pady=4)
        btn_finish.grid(row=0, column=1, padx=8, pady=4)

    def add_new_task(self):
        self.controller.show_frame("TaskFormPage")
        self.controller.frames["TaskFormPage"].event_generate_show()

    def finish_work(self):
        # إنهاء تشغيل الكود (إغلاق نافذة Tkinter)
        self.controller.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()
