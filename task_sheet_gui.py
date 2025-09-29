# -*- coding: utf-8 -*-
"""
Task Sheet GUI for Google Sheets
- التدفق: البداية -> اختيار التاريخ -> تعبئة نموذج المهمة -> ما بعد الإضافة
- المتطلبات: pip install gspread google-auth tkcalendar
- الثيم الداكن/النهاري (اختياري): pip install sv-ttk
- المصداقية: حفظ الصفوف باستخدام USER_ENTERED ليطبّق قواعد Google Sheets تلقائيًا.
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from datetime import datetime
from zoneinfo import ZoneInfo

import re
import time
import threading, queue

import gspread
from google.oauth2.service_account import Credentials

# محاولة استيراد sv_ttk (اختياري). إن لم يوجد، نستمر بدون كسر البرنامج.
try:
    import sv_ttk  # Sun Valley ttk theme
except Exception:
    sv_ttk = None

# ===================== الإعدادات =====================
# ملاحظة: حدّث المسار والـ Sheet/Worksheet حسب بيئتك
SERVICE_ACCOUNT_FILE = r"C:\Users\Naser Rahal\ServiceAccountKey\service_account.json"

# متغيّرات تُملأ من شاشة الإعداد
RUNTIME_SHEET_ID = None
RUNTIME_WORKSHEET_TITLE = None

# ترتيب الأعمدة في الشيت (يجب أن يطابق ترتيب الصف المُرسل)
HEADERS = [
    "Task ID", "The prompt", "Justification", "Feedback", "Rating", "Project", "Task duration (hour)", "Level", "Verdict",
    "Date", "Day", "Month", "Submitted time", "Date (US)", "Day (US)", "Month (US)", "Submitted time (US)", "OT",
]

# اختصارات الأشهر/الأيام (بالإنجليزية لتفادي مشاكل locale)
MONTH_ABBR = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
DAY_ABBR   = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# نمط Task ID المطلوب (24 خانة hex صغيرة)
HEX24_RE = re.compile(r'^[0-9a-f]{24}$')

# ===================== Google Sheets Helpers =====================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# كاش بسيط للورقة لتقليل فتح الاتصال في كل إضافة
_WS = None

LA_TZ = ZoneInfo("America/Los_Angeles")
JO_TZ = ZoneInfo("Asia/Amman")

def get_worksheet():
    """ارجع Worksheet باستخدام القيم المُعطاة من شاشة الإعداد."""
    global _WS, RUNTIME_SHEET_ID, RUNTIME_WORKSHEET_TITLE
    if _WS is not None:
        return _WS
    if not RUNTIME_SHEET_ID or not RUNTIME_WORKSHEET_TITLE:
        raise RuntimeError("Sheet ID/Worksheet title are not set yet.")

    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(RUNTIME_SHEET_ID)
    ws = sh.worksheet(RUNTIME_WORKSHEET_TITLE)

    header_row = ws.row_values(1)
    if not any(header_row):
        ws.insert_row(HEADERS, index=1)

    _WS = ws
    return ws

def append_task_row(row_values):
    """إضافة صف واحد إلى الشيت بخيار USER_ENTERED (يحاكي إدخال المستخدم)."""
    ws = get_worksheet()
    ws.append_row(row_values, value_input_option="USER_ENTERED")
    return ws

# كاش لمعرّفات المهام الموجودة
_TASK_IDS = None

def _load_task_ids(ws=None):
    """تحميل كل قيم العمود A (Task ID) كـ set في الكاش."""
    global _TASK_IDS
    if ws is None:
        ws = get_worksheet()
    vals = ws.col_values(1)[1:]  # تجاهل صفّ العناوين
    _TASK_IDS = {v.strip().lower() for v in vals if v and v.strip()}
    return _TASK_IDS

def task_id_exists(tid: str) -> bool:
    """التحقّق السريع من التكرار من الكاش (ويُحمّل أول مرة عند الحاجة)."""
    global _TASK_IDS
    if _TASK_IDS is None:
        _load_task_ids()
    return tid.strip().lower() in _TASK_IDS

def register_task_id(tid: str):
    """تحديث الكاش محليًا بعد نجاح الإضافة."""
    global _TASK_IDS
    if _TASK_IDS is None:
        _TASK_IDS = set()
    _TASK_IDS.add(tid.strip().lower())

# ===================== الواجهة =====================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("إدارة تسجيل المهام - Google Sheets")
        self.geometry("980x780")
        self.resizable(True, True)

        # بعد بناء الواجهات واستدعاء self.config(menu=menubar)
        self.update_idletasks()
        self.minsize(self.winfo_reqwidth(), self.winfo_reqheight())

        # --- الثيم والنمط العام ---
        self.style = ttk.Style()
        try:
            # ثيم افتراضي مستقر يعرض ألوان الحقول بوضوح
            self.style.theme_use("xpnative")
        except tk.TclError:
            pass

        BASE_FONT = ("Segoe UI", 11)
        TITLE_FONT = ("Segoe UI", 18, "bold")

        self.style.configure(".", font=BASE_FONT)
        self.style.configure("TButton", padding=(10, 6))
        self.style.configure("TLabel", padding=(2, 2))
        self.style.configure("Header.TLabel", font=TITLE_FONT)
        self.style.configure("Card.TLabelframe", padding=12)
        self.style.configure("Card.TLabelframe.Label", font=("Segoe UI", 12, "bold"))
        # حجم أكبر لقائمة OT
        self.style.configure("Big.TCombobox", font=("Segoe UI", 14))
        self.style.configure("StatsLine.TLabel", font=("Segoe UI", 14, "bold"))

        self.var_ot = tk.StringVar()  # القيمة الافتراضية، سيتم ضبطها تلقائيًا حسب لوس أنجلوس
        self.last_ot_us_date = None          # آخر يوم (LA) طُبّق عليه منطق الافتراضي
        self.ot_user_override_date = None    # اليوم (LA) الذي غيّر فيه المستخدم القيمة
        self.ot_user_override_value = None   # قيمة المستخدم لذلك اليوم

        # قيم افتراضية تُحفظ مؤقتًا داخل الجلسة
        self.last_defaults = {
            "Project": "",
            "Task duration (hour)": "",
            "Level": "",
            "Verdict": "",
        }

        self.session_submitted = 0  # عدد المهام المضافة منذ تشغيل التطبيق

        # شريط علوي
        self.topbar = tk.Frame(self, bg="#0ea5e9", height=52)
        self.topbar.grid(row=0, column=0, sticky="we")
        self.top_title = tk.Label(
            self.topbar, text="تسجيل مهام اليوم على Google Sheets",
            bg="#0ea5e9", fg="white", font=("Segoe UI", 16, "bold")
        )
        self.top_title.pack(side="top", padx=16)

        # الحاوية العامة للصفحات
        container = tk.Frame(self)
        
        container.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        # مهم: اسمح لإطار الصفحات نفسه بالتمدد
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # شريط الحالة
        self.status = tk.StringVar(value="")

        # تهيئة الصفحات
        self.frames = {}
        for F in (StartPage, SheetConfigPage, TaskFormPage, PostAddPage):
            frame = F(parent=container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # قائمة "عرض" للثيمات ووضع داكن/نهاري
        menubar = tk.Menu(self)
        view_menu = tk.Menu(menubar, tearoff=False)

        themes_menu = tk.Menu(view_menu, tearoff=False)
        for name in self.style.theme_names():
            themes_menu.add_command(label=name, command=lambda n=name: self._set_theme(n))
        view_menu.add_cascade(label="الثيمات (TTK)", menu=themes_menu)
        view_menu.add_separator()
        view_menu.add_command(label="تبديل الوضع الليلي/النهاري", command=self._toggle_dark)

        menubar.add_cascade(label="عرض", menu=view_menu)
        self.config(menu=menubar)

        self.show_frame("StartPage")

    def show_frame(self, name):
        frame = self.frames[name]
        frame.tkraise()
        try:
            frame.event_generate("<<ShowPage>>")
        except Exception:
            pass



    # -------- التحكم بالثيم ----------
    def _set_theme(self, name: str):
        try:
            # عند اختيار ثيم من قائمة TTK
            self.style.theme_use(name)
            self.status.set(f"Theme: {name}")
        except tk.TclError as e:
            messagebox.showerror("الثيم غير مدعوم", str(e))

    def _apply_light(self):
        """وضع نهاري."""
        self._dark = False
        if sv_ttk:
            sv_ttk.set_theme("light")
        else:
            try:
                self.style.theme_use("clam")
            except tk.TclError:
                pass
        if hasattr(self, "topbar"):
            self.topbar.configure(bg="#0ea5e9")
        if hasattr(self, "top_title"):
            self.top_title.configure(bg="#0ea5e9", fg="white")
        self._set_textwidgets_colors(bg="white", fg="black")

    def _apply_dark(self):
        """وضع داكن (يفضّل عبر sv_ttk إن توفّر)."""
        if sv_ttk:
            try:
                sv_ttk.set_theme("dark")
                self._dark = True
                if hasattr(self, "topbar"):
                    self.topbar.configure(bg="#111827")
                if hasattr(self, "top_title"):
                    self.top_title.configure(bg="#111827", fg="#e5e7eb")
                self._set_textwidgets_colors(bg="#111827", fg="#e5e7eb")
                return
            except Exception:
                pass

        # بديل يدوي بسيط إذا لم تتوفر sv_ttk
        self._dark = True
        bg, fg = "#1f2937", "#e5e7eb"
        self.style.configure(".", background=bg, foreground=fg)
        self.style.configure("TLabel", background=bg, foreground=fg)
        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabelframe", background=bg, foreground=fg)
        self.style.configure("Card.TLabelframe", background=bg)
        self.style.configure("Card.TLabelframe.Label", background=bg, foreground=fg)
        self.style.configure("TButton", background="#374151", foreground=fg)
        if hasattr(self, "topbar"):
            self.topbar.configure(bg="#111827")
        if hasattr(self, "top_title"):
            self.top_title.configure(bg="#111827", fg=fg)
        self._set_textwidgets_colors(bg="#111827", fg=fg)

    def _toggle_dark(self):
        if getattr(self, "_dark", False):
            self._apply_light()
        else:
            self._apply_dark()

    def _set_textwidgets_colors(self, bg, fg):
        """تلوين مربعات النص الكبيرة مع مؤشر الإدراج بما يناسب الثيم."""
        tf = self.frames.get("TaskFormPage")
        if tf:
            for w in (getattr(tf, "txt_prompt", None),
                      getattr(tf, "txt_just", None),
                      getattr(tf, "txt_feedback", None)):
                if w:
                    w.configure(bg=bg, fg=fg, insertbackground=fg)

# ---------------- صفحات الواجهة ----------------
class StartPage(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        lbl = ttk.Label(self, text="ابدأ العمل", style="Header.TLabel")
        lbl.pack(pady=40)

        btn = ttk.Button(self, text="ابدأ العمل", width=24,
                         command=lambda: controller.show_frame("SheetConfigPage"))
        btn.pack(pady=6)

class SheetConfigPage(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        title = ttk.Label(self, text="إعدادات Google Sheets", style="Header.TLabel")
        title.pack(pady=16)

        form = ttk.Frame(self); form.pack(pady=10, padx=12)

        ttk.Label(form, text="Spreadsheet ID:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        self.var_sheet_id = tk.StringVar()
        ent_id = ttk.Entry(form, textvariable=self.var_sheet_id, width=48, justify="left")
        ent_id.grid(row=0, column=1, sticky="we", padx=6, pady=6)

        ttk.Label(form, text="Worksheet title:").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        self.var_ws_title = tk.StringVar()
        ent_ws = ttk.Entry(form, textvariable=self.var_ws_title, width=48, justify="left")
        ent_ws.grid(row=1, column=1, sticky="we", padx=6, pady=6)

        form.columnconfigure(1, weight=1)

        ttk.Button(self, text="التالي", command=self.on_next).pack(pady=16)

    def on_next(self):
        sid = self.var_sheet_id.get().strip()
        wst = self.var_ws_title.get().strip()
        if not sid or not wst:
            messagebox.showerror("خطأ", "يرجى إدخال كلٍ من Spreadsheet ID وWorksheet title.")
            return

        # جرّب الاتصال للتحقق
        try:
            global RUNTIME_SHEET_ID, RUNTIME_WORKSHEET_TITLE, _WS, _TASK_IDS
            RUNTIME_SHEET_ID, RUNTIME_WORKSHEET_TITLE = sid, wst
            _WS = None
            try:
                _TASK_IDS = None  # لو كنت تستخدم كاش Task IDs للتكرار
            except NameError:
                pass
            get_worksheet()  # تأكيد صحة الإعداد
        except Exception as e:
            messagebox.showerror("فشل الاتصال", f"تعذّر فتح الورقة:\n{e}")
            return

        self.controller.show_frame("TaskFormPage")
        self.controller.frames["TaskFormPage"].event_generate_show()


class TaskFormPage(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        self._clock_job = None

        # الجديد:
        hdr_box = ttk.Frame(self)
        hdr_box.grid(row=0, column=1, columnspan=2, pady=(8, 4), sticky="n")

        # صندوق الوقت (US/LA) على اليسار - المربّع الأصفر
        left_info = ttk.Frame(self)
        left_info.grid(row=0, column=0, sticky="nw", padx=(8, 0), pady=(8, 0))
        self.lbl_us_time = ttk.Label(left_info, text="", style="StatsLine.TLabel", anchor="w", justify="left")
        self.lbl_us_time.pack()

        # صندوق الوقت (الأردن/عمّان) على اليمين - المربّع الأحمر
        right_info = ttk.Frame(self)
        right_info.grid(row=0, column=3, sticky="ne", padx=(0, 8), pady=(8, 0))
        self.lbl_jo_time = ttk.Label(right_info, text="", style="StatsLine.TLabel", anchor="e", justify="right")
        self.lbl_jo_time.pack()

        self.header = ttk.Label(
            hdr_box,
            text="إدخال تفاصيل المهمة",
            style="Header.TLabel",
            anchor="center",
            justify="center",
        )
        self.header.pack()

        # التاريخ المحلي (الأردن) في السطر الأول
        self.header_date_local = ttk.Label(
            hdr_box, text="", style="Header.TLabel", anchor="center", justify="center"
        )
        self.header_date_local.pack(pady=(4, 0))

        # تاريخ لوس أنجلِس في السطر الثاني تحت المحلي
        self.header_date_us = ttk.Label(
            hdr_box, text="", style="Header.TLabel", anchor="center", justify="center"
        )
        self.header_date_us.pack(pady=(2, 0))


        # ستايلات للتمييز البصري عند الخطأ
        _invalid_style = ttk.Style()
        _invalid_style.configure("Invalid.TEntry",    fieldbackground="#fee2e2")
        _invalid_style.configure("Invalid.TCombobox", fieldbackground="#fee2e2")

        # البطاقات
        left_card  = ttk.Labelframe(self, text="تفاصيل المهمة",   style="Card.TLabelframe")
        right_card = ttk.Labelframe(self, text="التقييم", style="Card.TLabelframe")
        meta_card  = ttk.Labelframe(self, text="بيانات المشروع",   style="Card.TLabelframe")

        left_card.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8, pady=6)
        right_card.grid(row=1, column=2, columnspan=2, sticky="nsew", padx=8, pady=6)
        meta_card.grid(row=2, column=0, columnspan=4, sticky="nsew", padx=8, pady=6)

        # اجعل أعمدة صفحة النموذج الأربعة تتمدّد بالتساوي (عمودان لليسار + عمودان لليمين)
        for c in (0, 1, 2, 3):
            self.columnconfigure(c, weight=1, uniform="cols")

        # الصف الذي يحوي البطاقتين يتمدّد رأسيًا
        self.rowconfigure(1, weight=1)

        # داخل البطاقة اليسرى: عمود النصوص يتمدّد، وصفّا النصوص يتمدّدان رأسيًا
        left_card.columnconfigure(0, weight=0)   # عمود العناوين
        left_card.columnconfigure(1, weight=1)   # عمود الحقول
        left_card.rowconfigure(1, weight=1)      # The prompt
        left_card.rowconfigure(2, weight=1)      # Justification

        # داخل البطاقة اليمنى: عمود الحقول يتمدّد، وصفّ Feedback يتمدّد رأسيًا
        right_card.columnconfigure(0, weight=0)  # عمود العناوين
        right_card.columnconfigure(1, weight=1)  # عمود الحقول
        right_card.rowconfigure(0, weight=1)     # Feedback

        # داخل بطاقة الميتاداتا: حقلا الإدخال يتمدّدان أفقيًا
        meta_card.columnconfigure(1, weight=1)   # Project
        meta_card.columnconfigure(3, weight=1)   # Task duration


        # -------- left_card --------
        ttk.Label(left_card, text="Task ID:", anchor="w", justify="left").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.var_task_id = tk.StringVar()
        self.entry_task_id = ttk.Entry(left_card, textvariable=self.var_task_id, width=36, justify="left")
        self.entry_task_id.grid(row=0, column=1, sticky="we", padx=6, pady=6)

        # تحقق لحظي: حتى 24 خانة [0-9a-fA-F]، والفراغ مسموح (أثناء الكتابة)
        _vcmd_hex = (self.register(lambda P: (P == "" or re.fullmatch(r"[0-9a-fA-F]{0,24}", P) is not None)), "%P")
        self.entry_task_id.configure(validate="key", validatecommand=_vcmd_hex)

        # لصق مُنظَّف (يحذف غير-hex، يقتطع إلى 24، يحوّل إلى حروف صغيرة)
        def _on_paste_tid(event=None):
            try:
                s = self.clipboard_get()
            except tk.TclError:
                return "break"
            clean = re.sub(r"[^0-9a-fA-F]", "", s)[:24].lower()
            self.var_task_id.set(clean)
            self.entry_task_id.icursor("end")
            self._update_add_state()
            return "break"

        self.entry_task_id.bind("<<Paste>>", _on_paste_tid)
        self.entry_task_id.bind("<Control-v>", _on_paste_tid)
        self.entry_task_id.bind("<Control-V>", _on_paste_tid)
        if self.tk.call("tk", "windowingsystem") == "aqua":
            self.entry_task_id.bind("<Command-v>", _on_paste_tid)

        ttk.Label(left_card, text="The prompt:", anchor="nw", justify="left").grid(row=1, column=0, sticky="nw", padx=6, pady=6)
        self.txt_prompt = scrolledtext.ScrolledText(left_card, width=44, height=5)
        self.txt_prompt.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)
        
        # اجعل المؤشر والكتابة من اليمين في خانة The prompt
        self.txt_prompt.configure(wrap="word")
        self.txt_prompt.tag_configure("align_right", justify="right")

        def _prompt_align_right(event=None):
            # طبّق محاذاة يمين على كل المحتوى
            self.txt_prompt.tag_add("align_right", "1.0", "end")
            # انقل المؤشر لنهاية السطر (يظهر يمينًا مع المحاذاة)
            self.txt_prompt.mark_set("insert", "end-1c")

        self.txt_prompt.bind("<FocusIn>", _prompt_align_right)
        self.txt_prompt.bind("<KeyRelease>", _prompt_align_right)

        # تطبيق أولي عند إنشاء الصفحة
        _prompt_align_right()

        ttk.Label(left_card, text="Justification:", anchor="nw", justify="left").grid(row=2, column=0, sticky="nw", padx=6, pady=6)
        self.txt_just = scrolledtext.ScrolledText(left_card, width=44, height=5)
        self.txt_just.grid(row=2, column=1, sticky="nsew", padx=6, pady=6)

        for c in (0, 1):
            left_card.grid_columnconfigure(c, weight=1)

        # -------- right_card --------
        ttk.Label(right_card, text="Feedback:", anchor="nw", justify="left").grid(row=0, column=0, sticky="nw", padx=6, pady=6)
        self.txt_feedback = scrolledtext.ScrolledText(right_card, width=44, height=5)
        self.txt_feedback.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

        ttk.Label(right_card, text="Rating:", anchor="w", justify="left").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        self.var_rating = tk.StringVar()
        self.cmb_rating = ttk.Combobox(
            right_card, textvariable=self.var_rating,
            values=["1", "2", "3", "4", "5"], state="readonly", justify="left"
        )
        self.cmb_rating.grid(row=1, column=1, sticky="we", padx=6, pady=6)

        self.cmb_rating.bind("<<ComboboxSelected>>", self._update_add_state)



        for c in (0, 1):
            right_card.grid_columnconfigure(c, weight=1)

        # -------- meta_card --------
        ttk.Label(meta_card, text="Project:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        self.var_project = tk.StringVar()
        self.cmb_project = ttk.Combobox(
            meta_card, textvariable=self.var_project,
            values=["hopper_code_rlhf", "apron_evals", "hopper_v2"],
            state="normal", justify="left"
        )
        self.cmb_project.grid(row=0, column=1, sticky="we", padx=6, pady=6)

        ttk.Label(meta_card, text="Level:").grid(row=0, column=2, sticky="e", padx=6, pady=6)
        self.var_level = tk.StringVar()
        self.cmb_level = ttk.Combobox(
            meta_card, textvariable=self.var_level,
            values=["reviewer", "tasker"], state="normal", justify="left"
        )
        self.cmb_level.grid(row=0, column=3, sticky="we", padx=6, pady=6)

        ttk.Label(meta_card, text="Verdict:").grid(row=0, column=4, sticky="e", padx=6, pady=6)
        self.var_verdict = tk.StringVar()
        self.cmb_verdict = ttk.Combobox(
            meta_card, textvariable=self.var_verdict, state="normal", justify="left",
            values=[
                "[Approve / Approve With Fixes] The task is now high quality: it has a good prompt, correct ratings, and a great final response.",
                "[Fixable] The task is mostly correct but requires adjustments to be done by a reviewer in the next review level",
                "[Reject] Cannot be fixed in the provided time. The task should be SBQed.",
                "[Approve] After my review/fix, the task is now high quality: it has a good prompt, good justifications, correct ratings, and a great final/selected response.",
                "[Reject] After reviewing this task I have determined that it cannot be fixed in the allotted time. I have written detailed feedback to the original attempter describing exactly what needs to be fixed.",
                "NONE",
            ]
        )
        self.cmb_verdict.grid(row=0, column=5, sticky="we", padx=6, pady=6)

        # تمكين التمدد الأفقي للحقلين
        for c in (1, 3, 5):
            meta_card.grid_columnconfigure(c, weight=1)
        # السماح بإضافة قيمة جديدة إلى قائمة أي Combobox عند كتابتها يدويًا
        def _ensure_in_values(combo: ttk.Combobox):
            val = combo.get().strip()
            if not val:
                return
            vals = list(combo.cget("values"))
            if val not in vals:
                vals.append(val)
                combo.configure(values=vals)

        for cmb in (self.cmb_level, self.cmb_verdict, self.cmb_project):
            cmb.bind("<<ComboboxSelected>>", lambda e, c=cmb: _ensure_in_values(c))
            cmb.bind("<FocusOut>",           lambda e, c=cmb: _ensure_in_values(c))
            
        # شريط المؤقت الكبير
        timer_bar = ttk.Frame(self)
        timer_bar.grid(row=3, column=0, columnspan=4, sticky="we", padx=8, pady=(0, 10))

        ttk.Label(timer_bar, text="Task duration:", anchor="center").pack(fill="x")
        self.timer_lbl = ttk.Label(timer_bar, text="00:00:00",
                                style="Header.TLabel", anchor="center",
                                font=("Segoe UI", 20, "bold"))
        self.timer_lbl.pack(fill="x")

        # أزرار التحكم
        buttons = ttk.Frame(self)
        buttons.grid(row=4, column=0, columnspan=4, pady=12)
        self.btn_add = ttk.Button(buttons, text="إضافة المهمة", command=self.on_add_task, state="disabled")
        self.btn_add.grid(row=0, column=1, padx=8)

        # سطر عدّاد مصغّر: الجملة + الرقم بجانبها
        self.var_stats_line = tk.StringVar(value="عدد المهام المسلّمة حتى الآن: 0")

        stats_box = ttk.Frame(self)
        stats_box.grid(row=3, column=3, rowspan=2, sticky="ne", padx=(0, 8), pady=(0, 10))

        ttk.Label(
            stats_box,
            textvariable=self.var_stats_line,
            style="StatsLine.TLabel",
            anchor="e",
            justify="right"
        ).pack(anchor="e")

        # --- OT: بجانب القائمة المنسدلة أسفل السطر مباشرة ---
        ot_row = ttk.Frame(stats_box)
        ot_row.pack(pady=(8, 0), anchor="e")

        ttk.Label(ot_row, text="OT:", anchor="e", justify="left")\
            .grid(row=0, column=0, sticky="e", padx=(0, 6))

        self.cmb_ot_in_form = ttk.Combobox(
            ot_row,
            textvariable=self.controller.var_ot,   # نفس متغير الحالة المستخدم سابقًا
            values=["Yes", "No"],
            state="readonly",
            width=8,
            justify="center",
            style="Big.TCombobox"
        )
        self.cmb_ot_in_form.grid(row=0, column=1, sticky="e")

        # ضبط أعمدة صف OT كي تبقى محاذاة لليمين
        ot_row.columnconfigure(0, weight=0)
        ot_row.columnconfigure(1, weight=0)
        # زر إعادة تعيين المؤقت تحت زر إضافة المهمة مباشرة
        self.btn_reset_timer = ttk.Button(
            buttons, text="إعادة تعيين المؤقت", command=self.on_reset_timer)
        self.btn_reset_timer.grid(row=1, column=1, padx=8, pady=(6, 0))


        self.cmb_ot_in_form.bind("<<ComboboxSelected>>", self._on_ot_user_selected)


        # صفّ اتصالات للخيط الخلفي + مؤشر تحميل
        self._q = queue.Queue()
        self.prog = ttk.Progressbar(self, length=220)
        self.prog.grid(row=5, column=0, columnspan=4, pady=(0, 8))
        self.prog.grid_remove()  # مخفي افتراضياً

        # تتبّع تغيّر القيم لتفعيل/تعطيل زر الإضافة وفق القواعد
        self.var_task_id.trace_add("write", self._update_add_state)
        self.var_rating.trace_add("write", self._update_add_state)

        # عند عرض الصفحة: تعبئة افتراضية وتحديث حالة الزر
        self.bind("<<ShowPage>>", self.on_show)

    def _on_ot_user_selected(self, event=None):
        # هذا يُستدعى فقط عند اختيار المستخدم من القائمة
        us_today = self._current_us_date()
        self.controller.ot_user_override_date = us_today
        self.controller.ot_user_override_value = self.controller.var_ot.get()

    # مساعد لإطلاق حدث العرض عند العودة للصفحة
    def event_generate_show(self):
        self.event_generate("<<ShowPage>>")

    def _refresh_tasks_count(self):
        self.var_stats_line.set(f"عدد المهام المسلّمة حتى الآن: {self.controller.session_submitted}")

    def on_show(self, event=None):
        """تعبئة القيم الافتراضية، وتحديث وقت الإرسال إن كان فارغًا، وتحديث حالة الزر."""
        d = self.controller.last_defaults
        self.var_project.set(d.get("Project", ""))
        self.var_level.set(d.get("Level", ""))
        self.var_verdict.set(d.get("Verdict", ""))
        
        self._timer_start()
                
        us_today = self._current_us_date()

        if self.controller.last_ot_us_date != us_today:
            # يوم جديد في LA (أو أول مرة): طبّق الافتراضي ثم صفّر حالة override
            self._set_ot_default_from_la_now()
            self.controller.last_ot_us_date = us_today
            self.controller.ot_user_override_date = None
            self.controller.ot_user_override_value = None
        else:
            # نفس اليوم في LA:
            if self.controller.ot_user_override_date == us_today and self.controller.ot_user_override_value:
                # احترم اختيار المستخدم لنفس اليوم
                self.controller.var_ot.set(self.controller.ot_user_override_value)
            else:
                # لا يوجد override (المستخدم لم يغيّر): أبقِ/أعد الافتراضي إن كانت فارغة
                if not self.controller.var_ot.get():
                    self._set_ot_default_from_la_now()

        self._update_add_state()
        self._update_header_dates()
        self._refresh_tasks_count()

        # ألغِ أي مؤقّت سابق ثم ابدأ التحديثات
        if getattr(self, "_clock_job", None):
            try: self.after_cancel(self._clock_job)
            except Exception: pass
        self._tick_clocks()


    # تمييز الحقول بصريًا عند الخطأ (يدعم Entry وCombobox)
    def _mark_valid(self, widget, ok: bool):
        if not widget:
            return
        style_name = "Invalid.TCombobox" if isinstance(widget, ttk.Combobox) else "Invalid.TEntry"
        try:
            widget.configure(style="" if ok else style_name)
        except Exception:
            pass


    def _validate_all(self, show_msg: bool = False) -> bool:
        tid_raw = self.var_task_id.get().strip()
        tid = tid_raw.lower()
        if tid != tid_raw:
            self.var_task_id.set(tid)

        rating = self.var_rating.get().strip()

        ok_tid    = bool(HEX24_RE.fullmatch(tid))
        ok_rating = (rating == "") or rating.isdigit()

        # تحقّق تكرار Task ID من الكاش
        ok_unique = True
        if ok_tid:
            try:
                ok_unique = not task_id_exists(tid)
            except Exception:
                ok_unique = True

        # تلوين الحقول
        rating_widget = getattr(self, "cmb_rating", None)
        self._mark_valid(self.entry_task_id, ok_tid and ok_unique)
        self._mark_valid(rating_widget, ok_rating)

        if show_msg:
            if not ok_tid:
                messagebox.showerror("تحقق المدخلات", "Task ID يجب أن يطابق ^[0-9a-f]{24}$")
                return False
            if not ok_unique:
                messagebox.showerror("تحقق المدخلات", "Task ID موجود مسبقًا في الشيت.")
                return False
            if not ok_rating:
                messagebox.showerror("تحقق المدخلات", "rating (اختياري) يجب أن يكون رقمًا صحيحًا.")
                return False

        return ok_tid and ok_unique and ok_rating


    def _update_add_state(self, *args):
        """تفعيل زر الإضافة فقط عندما تتحقق القواعد أعلاه."""
        can_enable = self._validate_all(show_msg=False)
        self.btn_add.config(state="normal" if can_enable else "disabled")
   

    def _set_busy(self, busy: bool):
        # تعطيل/تمكين كل العناصر في الصفحة أثناء الإرسال
        def _toggle(widget):
            try:
                # عناصر ttk القابلة للتعطيل
                if isinstance(widget, (ttk.Entry, ttk.Button, ttk.Combobox, ttk.Labelframe, ttk.Frame, ttk.Label)):
                    widget_state = "disabled" if busy else "normal"
                    # ليس لكل العناصر state؛ جرّب آمن
                    try: widget.configure(state=widget_state)
                    except tk.TclError: pass
                # صناديق النص
                if isinstance(widget, scrolledtext.ScrolledText):
                    widget.configure(state="disabled" if busy else "normal")
            except Exception:
                pass
            # كرّر على الأبناء
            for child in widget.winfo_children():
                _toggle(child)
        _toggle(self)
        # أبقِ شريط التقدّم مفعلاً حتى لو بقية العناصر معطّلة
        try: self.prog.configure(state="normal")
        except tk.TclError: pass

    def _worker_append(self, row):
        try:
            ws = get_worksheet()
            # تحقّق نهائي مضاد لظروف التسابق: اقرأ العمود A من الشيت مباشرة
            existing = {v.strip().lower() for v in ws.col_values(1)[1:] if v and v.strip()}
            tid = (row[0] or "").strip().lower()
            if tid in existing:
                self._q.put(("dup", tid))  # أبلغ الخيط الرئيسي بوجود تكرار
                return

            ws.append_row(row, value_input_option="USER_ENTERED")
            register_task_id(tid)        # حدّث الكاش محليًا بعد النجاح
            self._q.put(("ok", ws))
        except Exception as e:
            self._q.put(("err", str(e)))


    def _poll_append(self):
        try:
            status, payload = self._q.get_nowait()
        except queue.Empty:
            self.after(120, self._poll_append)
            return
        
        duration_hours = f"{self._timer_hours():.2f}"  # مثال: 0.75 ساعة

        # توقيف وإخفاء المؤشر ثم إعادة التفاعل أو الانتقال
        self.prog.stop()
        self.prog.grid_remove()

        # فكّ التعطيل قبل التفريغ
        self._set_busy(False)

        if status == "ok":
            ws = payload
            # حفظ الافتراضيات
            self.controller.last_defaults["Project"] = self.var_project.get().strip()
            self.controller.last_defaults["Level"] = self.var_level.get().strip()
            self.controller.last_defaults["Verdict"] = self.var_verdict.get().strip()
            self.controller.session_submitted += 1
            self._refresh_tasks_count()

            # تحديث الحالة (إن موجود)
            if hasattr(self.controller, "status"):
                self.controller.status.set(f"✓ Added to: {ws.spreadsheet.title} / {ws.title} - duration {duration_hours}")

            # تفريغ الحقول غير الافتراضية
            self.var_task_id.set("")
            self.txt_prompt.delete("1.0", "end")
            self.txt_just.delete("1.0", "end")
            self.txt_feedback.delete("1.0", "end")
            self.var_rating.set("")

            # الانتقال لصفحة النجاح
            self.controller.show_frame("PostAddPage")

        elif status == "dup":
            self._set_busy(False)
            self._timer_start()  # اختياري: استئناف المؤقّت بعد إلغاء الإرسال
            messagebox.showerror("مكرر", f"Task ID موجود مسبقًا في الشيت: {payload}")
        else:
            # خطأ: أعد التفاعل وأظهر رسالة
            self._set_busy(False)
            messagebox.showerror("فشل الإضافة", f"حدث خطأ أثناء الإضافة إلى Google Sheets:\n{payload}")


    def on_add_task(self):

        # بوابة نهائية: في حال وجود أخطاء يمنع الإرسال ويعرض الرسائل
        if not self._validate_all(show_msg=True):
            return

        self._timer_stop()
        duration_hours = f"{self._timer_hours():.2f}"  # مثال: 0.75 ساعة

        # الحقول النصية الكبيرة
        prompt = self.txt_prompt.get("1.0", "end").strip()
        just   = self.txt_just.get("1.0", "end").strip()
        feed   = self.txt_feedback.get("1.0", "end").strip()

        # وقت الآن محلي (الأردن)
        jo = JO_TZ
        now_jo = datetime.now(jo)
        submitted_now = now_jo.strftime("%H:%M")            # Submitted time (محلي)
        local_date  = now_jo.strftime("%Y-%m-%d")
        local_day   = DAY_ABBR[now_jo.weekday()]
        local_month = MONTH_ABBR[now_jo.month - 1]

        la = LA_TZ
        us_now = datetime.now(la)
        submitted_us = us_now.strftime("%H:%M")

        us_date = us_now.strftime("%Y-%m-%d")
        us_day_abbr = DAY_ABBR[us_now.weekday()]
        us_month_abbr = MONTH_ABBR[us_now.month - 1]

        # بناء الصف بنفس ترتيب HEADERS
        row = [
            self.var_task_id.get().strip(),
            prompt,
            just,
            feed,
            self.var_rating.get().strip(),
            self.var_project.get().strip(),
            duration_hours,
            self.var_level.get().strip(),
            self.var_verdict.get().strip(),
            local_date,
            local_day,
            local_month, 
            submitted_now,
            us_date,            # Date (US)
            us_day_abbr,        # Day (US)
            us_month_abbr,      # Month (US)
            submitted_us,        # Submitted time (US)
            self.controller.var_ot.get().strip(),   # OT
        ]
        
        # إظهار المؤشر وتعطيل الصفحة ثم الإرسال في خيط
        self._set_busy(True)
        self.prog.grid()
        self.prog.start()

        t = threading.Thread(target=self._worker_append, args=(row,), daemon=True)
        t.start()
        self.after(120, self._poll_append)
        return
    
    def on_reset_timer(self):
    # رسالة تأكيد قبل إعادة التعيين
        if messagebox.askyesno("تأكيد", "هل تريد إعادة تعيين المؤقت؟"):
            # إيقاف المؤقت الحالي (إن كان يعمل)، تصفيره، ثم بدء العد من جديد
            try:
                self._timer_stop()
            except Exception:
                pass
            self._timer_reset()
            self._timer_start()

    # ======== مؤقت المدة ========
    def _timer_reset(self):
        self._timer_running = False
        self._t0 = None
        self._elapsed_base = 0.0   # ثوانٍ متراكمة
        self.timer_lbl.configure(text="00:00:00")

    def _timer_start(self):
        # يبدأ من الصفر في كل عرض للصفحة
        self._timer_reset()
        self._timer_running = True
        self._t0 = time.perf_counter()
        self.after(1000, self._timer_tick)

    def _timer_tick(self):
        if not self._timer_running or self._t0 is None:
            return
        now = time.perf_counter()
        total = self._elapsed_base + (now - self._t0)
        h = int(total // 3600)
        m = int((total % 3600) // 60)
        s = int(total % 60)
        self.timer_lbl.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        self.after(1000, self._timer_tick)

    def _timer_stop(self):
        if self._timer_running and self._t0 is not None:
            self._elapsed_base += (time.perf_counter() - self._t0)
            self._timer_running = False
            self._t0 = None

    def _timer_hours(self) -> float:
        # يعيد المدة الحالية بالساعات (عدد عشري)
        total = self._elapsed_base
        if self._timer_running and self._t0 is not None:
            total += (time.perf_counter() - self._t0)
        return total / 3600.0
    
    def _set_ot_default_from_la_now(self):
        la = LA_TZ
        wd = datetime.now(la).weekday()  # Mon=0..Sun=6
        self.controller.var_ot.set("Yes" if wd in (4, 5) else "No") 

    def _current_us_date(self) -> str:
        la = LA_TZ
        return datetime.now(la).date().isoformat()  # "YYYY-MM-DD"
    
    def _update_header_dates(self):
        # عمّان (محلي)
        jo = JO_TZ
        now_jo = datetime.now(jo)
        day_local = DAY_ABBR[now_jo.weekday()]            # Mon..Sun
        self.header_date_local.configure(
            text=f"{day_local} - {now_jo.strftime('%Y-%m-%d')} (JOR)"
        )

        # لوس أنجلِس (US)
        la = LA_TZ
        now_la = datetime.now(la)
        day_us = DAY_ABBR[now_la.weekday()]
        self.header_date_us.configure(
            text=f"{day_us} - {now_la.strftime('%Y-%m-%d')} (US)"
        )


    def _tick_clocks(self):
        # US (Los Angeles) time 24h
        la = LA_TZ
        now_la = datetime.now(la).strftime("%H:%M:%S")
        self.lbl_us_time.configure(text=f"الوقت الآن (لوس أنجلِس): {now_la}")

        # Jordan (Amman) time 24h
        jo = JO_TZ
        now_jo = datetime.now(jo).strftime("%H:%M:%S")
        self.lbl_jo_time.configure(text=f"الوقت الآن (الأردن): {now_jo}")

        # حدّث التاريخ/اليوم الأمريكي تحت العنوان
        # self._update_header_us_date()

        # حدّث كل ثانية
        self._clock_job = self.after(1000, self._tick_clocks)


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

        # بعد btn_finish.grid(...)
        self.result_lbl = ttk.Label(
            self,
            textvariable=controller.status,
            anchor="center",
            justify="center",
            font=("Segoe UI", 18, "bold"),
            foreground = "#32a852",
            wraplength=900,  # التفاف اختياري إذا كان العنوان طويلًا
        )
        self.result_lbl.pack(pady=20, fill="x")


    def add_new_task(self):
        # العودة لنفس التاريخ مع بقاء القيم الافتراضية
        self.controller.show_frame("TaskFormPage")
        self.controller.frames["TaskFormPage"].event_generate_show()

    def finish_work(self):
        # إغلاق نافذة التطبيق
        self.controller.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()
