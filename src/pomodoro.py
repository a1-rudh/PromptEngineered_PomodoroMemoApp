import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import time
import threading
from datetime import datetime, timedelta
import os
import re
from pathlib import Path

APP_NAME = "Pomodoro Memo App"

# Default durations (minutes)
DEFAULTS = {
    "work": 25,
    "short": 5,
    "long": 15,
    "cycles_before_long": 4
}

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
TASK_DIR = LOG_DIR / "tasks"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TASK_DIR.mkdir(parents=True, exist_ok=True)

KEYWORDS_DONT = ["scroll", "instagram", "tiktok", "reel", "youtube", "doom", "binge", "gaming", "whatsapp", "twitter", "x.com", "reddit"]
KEYWORDS_DO = ["walk", "water", "stretch", "breath", "breathing", "hydrate", "standing", "sunlight", "tea", "coffee", "pushups", "plank", "yoga"]

def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[\\/:*?\"<>|]+", "-", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:80] if len(name) > 80 else name

def now():
    return datetime.now()

def fmt(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S")

def md_h2(text): return f"## {text}\n\n"
def md_h3(text): return f"### {text}\n\n"
def md_kv(k, v): return f"- **{k}**: {v}\n"

def analyze_break_activity(text: str):
    text_l = text.lower()
    dos = []
    donts = []

    if any(k in text_l for k in KEYWORDS_DONT):
        donts.append("Avoid algorithmic feeds and passive scrolling next break.")
        donts.append("Keep phone in another room or enable Focus mode.")
    if any(k in text_l for k in KEYWORDS_DO):
        dos.append("Repeat quick movement or hydration — it helped reset focus.")
    # neutral suggestions
    if not dos and not donts:
        dos.append("Keep break short (3–5 min) and physically reset (stand/stretch).")
        dos.append("Sip water; avoid snacks if they cause lethargy.")
    return dos, donts

class SessionLogger:
    def __init__(self):
        self.day_file = LOG_DIR / f"Pomodoro_{now().strftime('%Y-%m-%d')}.md"

    def append_markdown(self, text: str):
        with open(self.day_file, "a", encoding="utf-8") as f:
            f.write(text)

    def append_task(self, task_name: str, text: str):
        if not task_name:
            return
        fname = sanitize_filename(task_name) + ".md"
        with open(TASK_DIR / fname, "a", encoding="utf-8") as f:
            f.write(text)

class MemoDialog(tk.Toplevel):
    def __init__(self, master, title: str, placeholder: str = "", initial: str = ""):
        super().__init__(master)
        self.title(title)
        self.geometry("520x360")
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()
        self.result = None

        lbl = tk.Label(self, text=placeholder, anchor="w")
        lbl.pack(fill="x", padx=10, pady=(10, 4))

        self.text = tk.Text(self, wrap="word")
        self.text.pack(expand=True, fill="both", padx=10, pady=(0, 10))
        if initial:
            self.text.insert("1.0", initial)

        btns = tk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(btns, text="Save", width=10, command=self.on_ok).pack(side="right", padx=4)
        tk.Button(btns, text="Cancel", width=10, command=self.on_cancel).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def on_ok(self):
        self.result = self.text.get("1.0", "end").strip()
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()

class PomodoroApp:
    def __init__(self, root):
        self.root = root
        root.title(APP_NAME)
        root.geometry("420x420")

        self.logger = SessionLogger()

        # State
        self.mode = "work"  # "work" | "short" | "long"
        self.running = False
        self.remaining = DEFAULTS["work"] * 60
        self.timer_thread = None
        self.stop_flag = False
        self.completed_work_sessions = 0

        self.session_start_ts = None
        self.last_mode_start = None
        self.task_start_ts = None

        # Header / Task name
        top = tk.Frame(root)
        top.pack(fill="x", padx=12, pady=8)
        tk.Label(top, text="Task Name:").pack(side="left")
        self.task_var = tk.StringVar(value="")
        self.task_entry = tk.Entry(top, textvariable=self.task_var)
        self.task_entry.pack(side="left", expand=True, fill="x", padx=6)

        # Mode selection
        mode_frame = tk.Frame(root)
        mode_frame.pack(pady=(0, 6))
        self.mode_var = tk.StringVar(value="work")
        for text, val in [("Work", "work"), ("Short Break", "short"), ("Long Break", "long")]:
            ttk.Radiobutton(mode_frame, text=text, value=val, variable=self.mode_var, command=self.on_mode_change).pack(side="left", padx=6)

        # Time display
        self.time_label = tk.Label(root, text="25:00", font=("Segoe UI", 40, "bold"))
        self.time_label.pack(pady=6)

        # Cycle label
        self.cycle_label = tk.Label(root, text="Cycle 0 • Paused", fg="#666")
        self.cycle_label.pack()

        # Buttons
        btns = tk.Frame(root)
        btns.pack(pady=8)
        self.start_btn = ttk.Button(btns, text="Start", command=self.toggle_start)
        self.start_btn.pack(side="left", padx=6)
        ttk.Button(btns, text="Skip", command=self.skip).pack(side="left", padx=6)
        ttk.Button(btns, text="Reset", command=self.reset).pack(side="left", padx=6)

        # Settings
        setf = tk.LabelFrame(root, text="Settings")
        setf.pack(fill="x", padx=12, pady=10)
        self.work_var = tk.StringVar(value=str(DEFAULTS["work"]))
        self.short_var = tk.StringVar(value=str(DEFAULTS["short"]))
        self.long_var = tk.StringVar(value=str(DEFAULTS["long"]))
        self.cbl_var = tk.StringVar(value=str(DEFAULTS["cycles_before_long"]))
        self.auto_var = tk.BooleanVar(value=False)

        self._add_setting(setf, "Work (min)", self.work_var, 0)
        self._add_setting(setf, "Short Break (min)", self.short_var, 1)
        self._add_setting(setf, "Long Break (min)", self.long_var, 2)
        self._add_setting(setf, "Cycles before long break", self.cbl_var, 3)
        ttk.Checkbutton(setf, text="Auto-start next session", variable=self.auto_var).grid(row=4, column=0, columnspan=2, sticky="w", padx=8, pady=(4,8))

        # Initialize
        self.on_mode_change()
        self.task_start_ts = now()

    def _add_setting(self, parent, label, var, row):
        tk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(parent, textvariable=var, width=8).grid(row=row, column=1, sticky="w", padx=8, pady=4)

    def on_mode_change(self):
        self.mode = self.mode_var.get()
        minutes = self._current_default_minutes()
        self.remaining = minutes * 60
        self.last_mode_start = now()
        self._update_time_label()
        self._update_status()

    def _current_default_minutes(self):
        def parse_int(var, default):
            try:
                v = int(var.get())
                if 1 <= v <= 300: return v
            except: pass
            return default

        if self.mode == "work":
            return parse_int(self.work_var, DEFAULTS["work"])
        elif self.mode == "short":
            return parse_int(self.short_var, DEFAULTS["short"])
        else:
            return parse_int(self.long_var, DEFAULTS["long"])

    def toggle_start(self):
        if not self.running:
            self.start()
        else:
            self.pause()

    def start(self):
        if not self.running:
            self.running = True
            self.stop_flag = False
            self.start_btn.config(text="Pause")
            if self.session_start_ts is None:
                self.session_start_ts = now()
            self.last_mode_start = now()
            self._update_status()
            self.timer_thread = threading.Thread(target=self._run_timer, daemon=True)
            self.timer_thread.start()

    def pause(self):
        if self.running:
            self.running = False
            self.stop_flag = True
            self.start_btn.config(text="Start")
            self._update_status()

    def skip(self):
        self.pause()
        self._complete_session(skipped=True)
        self._goto_next_session()
        if self.auto_var.get():
            self.start()

    def reset(self):
        self.pause()
        self.completed_work_sessions = 0
        self.session_start_ts = None
        self.on_mode_change()

    def _run_timer(self):
        while self.running and not self.stop_flag and self.remaining > 0:
            time.sleep(1)
            self.remaining -= 1
            self.root.after(0, self._update_time_label)

        if self.running and not self.stop_flag and self.remaining <= 0:
            self.root.after(0, self._on_times_up)

    def _on_times_up(self):
        self.pause()
        self._complete_session(skipped=False)
        self._goto_next_session()
        if self.auto_var.get():
            self.start()

    def _update_time_label(self):
        mins, secs = divmod(max(0, self.remaining), 60)
        self.time_label.config(text=f"{mins:02}:{secs:02}")

    def _update_status(self):
        run = "Running" if self.running else "Paused"
        self.cycle_label.config(text=f"Cycle {self.completed_work_sessions} • {run}")

    def _complete_session(self, skipped=False):
        start = self.last_mode_start or now()
        end = now()
        duration = int((end - start).total_seconds())
        task = self.task_var.get().strip()

        if self.mode == "work":
            if not skipped:
                memo = self._prompt_memo("Work session finished 🎯", "What did you study / do this session?")
            else:
                memo = None
            self.completed_work_sessions += 1
            self._write_markdown_block(
                mode="Work",
                start=start, end=end, duration_s=duration,
                task=task,
                memo=memo,
                extra=None
            )
        else:
            # Break completion
            if not skipped:
                memo = self._prompt_memo("Break finished ☕", "What did you do during the break? (optional)")
            else:
                memo = None
            dos, donts = analyze_break_activity(memo or "")
            extra = ""
            if dos or donts:
                extra += "#### Do\n\n" + "\n".join([f"- {d}" for d in dos]) + "\n\n"
                extra += "#### Don't\n\n" + "\n".join([f"- {d}" for d in donts]) + "\n\n"
            self._write_markdown_block(
                mode="Short Break" if self.mode == "short" else "Long Break",
                start=start, end=end, duration_s=duration,
                task=task,
                memo=memo,
                extra=extra if extra else None
            )

    def _prompt_memo(self, title, placeholder):
        dlg = MemoDialog(self.root, title=title, placeholder=placeholder)
        self.root.wait_window(dlg)
        return dlg.result

    def _write_markdown_block(self, mode, start, end, duration_s, task, memo, extra=None):
        mins = duration_s // 60
        secs = duration_s % 60
        ts_day = now().strftime("%Y-%m-%d")
        header = f"## {mode} • {fmt(start)} → {fmt(end)} ({mins}m {secs}s)\n\n"
        meta = ""
        meta += md_kv("Task", task or "(unnamed)")
        meta += md_kv("Start", fmt(start))
        meta += md_kv("End", fmt(end))
        meta += md_kv("Duration", f"{mins}m {secs}s")
        meta += "\n"

        body = ""
        if memo:
            body += "#### Memo\n\n"
            body += memo.strip() + "\n\n"

        if extra:
            body += extra

        block = header + meta + body + "---\n\n"

        # Append to daily log
        with open(LOG_DIR / f"Pomodoro_{ts_day}.md", "a", encoding="utf-8") as f:
            # Add file title if new
            if f.tell() == 0:
                f.write(f"# Pomodoro Log — {ts_day}\n\n")
            f.write(block)

        # Append to task log
        if task:
            tname = sanitize_filename(task) + ".md"
            tpath = TASK_DIR / tname
            is_new = not tpath.exists() or tpath.stat().st_size == 0
            with open(tpath, "a", encoding="utf-8") as f:
                if is_new:
                    f.write(f"# Task Log — {task}\n\n")
                f.write(block)

    def _goto_next_session(self):
        # After work -> short/long. After break -> work.
        if self.mode == "work":
            try:
                cycles_before_long = max(1, int(self.cbl_var.get()))
            except:
                cycles_before_long = DEFAULTS["cycles_before_long"]
            if self.completed_work_sessions % cycles_before_long == 0:
                self.mode_var.set("long")
            else:
                self.mode_var.set("short")
        else:
            self.mode_var.set("work")
        self.on_mode_change()

if __name__ == "__main__":
    root = tk.Tk()
    app = PomodoroApp(root)
    root.mainloop()