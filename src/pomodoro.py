import tkinter as tk
from tkinter import messagebox, simpledialog, ttk, filedialog
import time
import threading
from datetime import datetime, timedelta
import os
import re
from pathlib import Path
import sys

APP_NAME = "Pomodoro Memo App"

# Default durations (minutes)
DEFAULTS = {
    "work": 25,
    "short": 5,
    "long": 15,
    "cycles_before_long": 4
}

# Logging folders (created next to this file)
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

def md_kv(k, v): return f"- **{k}**: {v}\n"

def analyze_break_activity(text: str):
    text_l = text.lower()
    dos, donts = [], []
    if any(k in text_l for k in KEYWORDS_DONT):
        donts.append("Avoid algorithmic feeds and passive scrolling next break.")
        donts.append("Keep phone in another room or enable Focus mode.")
    if any(k in text_l for k in KEYWORDS_DO):
        dos.append("Repeat quick movement or hydration — it helped reset focus.")
    if not dos and not donts:
        dos.append("Keep break short (3–5 min) and physically reset (stand/stretch).")
        dos.append("Sip water; avoid snacks if they cause lethargy.")
    return dos, donts

class SessionLogger:
    def __init__(self):
        self._sync_day_file()

    def _sync_day_file(self):
        self.day_file = LOG_DIR / f"Pomodoro_{now().strftime('%Y-%m-%d')}.md"

    def append_markdown(self, text: str):
        # Ensure day file matches today
        self._sync_day_file()
        new_file = not self.day_file.exists() or self.day_file.stat().st_size == 0
        with open(self.day_file, "a", encoding="utf-8") as f:
            if new_file:
                f.write(f"# Pomodoro Log — {now().strftime('%Y-%m-%d')}\n\n")
            f.write(text)

    def append_task(self, task_name: str, text: str):
        if not task_name:
            return
        fname = sanitize_filename(task_name) + ".md"
        tpath = TASK_DIR / fname
        is_new = not tpath.exists() or tpath.stat().st_size == 0
        with open(tpath, "a", encoding="utf-8") as f:
            if is_new:
                f.write(f"# Task Log — {task_name}\n\n")
            f.write(text)

class MemoDialog(tk.Toplevel):
    """Modal memo dialog with explicit Save/Skip + keyboard shortcuts."""
    def __init__(self, master, title: str, placeholder: str = "", initial: str = ""):
        super().__init__(master)
        self.title(title)
        self.geometry("560x380")
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()
        self.result = None  # None = skipped; str = saved memo

        header = tk.Frame(self)
        header.pack(fill="x", padx=10, pady=(10, 6))
        tk.Label(header, text=placeholder, anchor="w").pack(side="left", fill="x", expand=True)

        self.text = tk.Text(self, wrap="word", font=("Segoe UI", 10))
        self.text.pack(expand=True, fill="both", padx=10, pady=(0, 6))
        if initial:
            self.text.insert("1.0", initial)

        hint = tk.Label(self, text="Tips: Ctrl+Enter or Ctrl+S = Save & Continue • Esc = Skip", fg="#666")
        hint.pack(fill="x", padx=10, pady=(0, 6))

        btns = tk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        save_btn = ttk.Button(btns, text="Save & Continue", command=self.on_save)
        save_btn.pack(side="right", padx=6)
        skip_btn = ttk.Button(btns, text="Skip", command=self.on_skip)
        skip_btn.pack(side="right")

        # Key bindings
        self.bind("<Control-Return>", lambda e: self.on_save())
        self.bind("<Control-s>", lambda e: self.on_save())
        self.bind("<Escape>", lambda e: self.on_skip())

        self.protocol("WM_DELETE_WINDOW", self.on_skip)
        self.after(50, self.text.focus_set)

    def on_save(self):
        self.result = self.text.get("1.0", "end").strip()
        self.destroy()

    def on_skip(self):
        self.result = None
        self.destroy()

def play_tone_sequence(theme: str, event: str, root: tk.Tk):
    """Plays a short tone sequence using winsound; falls back to tk.bell()."""
    try:
        import winsound
        if theme == "Beep":
            if event == "start":
                winsound.Beep(880, 120); winsound.Beep(988, 150)
            else:
                winsound.Beep(784, 120); winsound.Beep(659, 120); winsound.Beep(523, 180)
        else:
            if event == "start":
                winsound.Beep(740, 140); winsound.Beep(880, 180)
            else:
                winsound.Beep(659, 120); winsound.Beep(587, 160); winsound.Beep(523, 220)
    except Exception:
        try: root.bell()
        except Exception: pass

class PomodoroApp:
    def __init__(self, root):
        self.root = root
        root.title(APP_NAME)
        root.geometry("480x500")

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

        # Menu
        menubar = tk.Menu(root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Save Logs…", command=self.save_logs_dialog)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=root.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        root.config(menu=menubar)

        # Header / Task name
        top = tk.Frame(root)
        top.pack(fill="x", padx=12, pady=8)
        tk.Label(top, text="Task Name:").pack(side="left")
        self.task_var = tk.StringVar(value="")
        self.task_entry = tk.Entry(top, textvariable=self.task_var)
        self.task_entry.pack(side="left", expand=True, fill="x", padx=6)
        ttk.Button(top, text="Save Logs…", command=self.save_logs_dialog).pack(side="right")

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
        self.sound_var = tk.BooleanVar(value=True)
        self.sound_theme = tk.StringVar(value="SoftChime")

        self._add_setting(setf, "Work (min)", self.work_var, 0)
        self._add_setting(setf, "Short Break (min)", self.short_var, 1)
        self._add_setting(setf, "Long Break (min)", self.long_var, 2)
        self._add_setting(setf, "Cycles before long break", self.cbl_var, 3)
        ttk.Checkbutton(setf, text="Auto-start next session", variable=self.auto_var).grid(row=4, column=0, columnspan=2, sticky="w", padx=8, pady=(4,4))
        ttk.Checkbutton(setf, text="Play sounds", variable=self.sound_var).grid(row=5, column=0, sticky="w", padx=8, pady=(4,4))
        tk.Label(setf, text="Sound theme").grid(row=5, column=1, sticky="w", padx=8)
        ttk.Combobox(setf, textvariable=self.sound_theme, values=["Beep", "SoftChime"], state="readonly", width=12).grid(row=5, column=1, sticky="e", padx=8)

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
        if not self.running: self.start()
        else: self.pause()

    def start(self):
        if self.running: return
        self.running = True
        self.stop_flag = False
        self.start_btn.config(text="Pause")
        if self.session_start_ts is None:
            self.session_start_ts = now()
        self.last_mode_start = now()
        self._update_status()
        if self.sound_var.get():
            self.root.after(0, lambda: play_tone_sequence(self.sound_theme.get(), "start", self.root))
        self.timer_thread = threading.Thread(target=self._run_timer, daemon=True)
        self.timer_thread.start()

    def pause(self):
        if not self.running: return
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
        if self.sound_var.get():
            play_tone_sequence(self.sound_theme.get(), "end", self.root)
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

        # Prompt memo with explicit Save/Skip when not skipped
        memo = None
        if not skipped:
            if self.mode == "work":
                memo = self._prompt_memo("Work session finished 🎯", "What did you study / do this session?")
            else:
                memo = self._prompt_memo("Break finished ☕", "What did you do during the break? (optional)")

        # Build block
        mins = duration // 60
        secs = duration % 60
        header = f"## {('Work' if self.mode=='work' else ('Short Break' if self.mode=='short' else 'Long Break'))} • {fmt(start)} → {fmt(end)} ({mins}m {secs}s)\n\n"
        meta = ""
        meta += md_kv("Task", task or "(unnamed)")
        meta += md_kv("Start", fmt(start))
        meta += md_kv("End", fmt(end))
        meta += md_kv("Duration", f"{mins}m {secs}s")
        meta += "\n"

        body = ""
        if memo:
            body += "#### Memo\n\n" + memo.strip() + "\n\n"
            # For break memos, add Do/Don't
            if self.mode != "work":
                dos, donts = analyze_break_activity(memo)
                if dos:
                    body += "#### Do\n\n" + "\n".join([f"- {d}" for d in dos]) + "\n\n"
                if donts:
                    body += "#### Don't\n\n" + "\n".join([f"- {d}" for d in donts]) + "\n\n"

        block = header + meta + body + "---\n\n"

        # Write immediately to logs
        self.logger.append_markdown(block)
        if task:
            self.logger.append_task(task, block)

        # Advance counters
        if self.mode == "work":
            self.completed_work_sessions += 1

    def _prompt_memo(self, title, placeholder):
        dlg = MemoDialog(self.root, title=title, placeholder=placeholder)
        self.root.wait_window(dlg)
        return dlg.result  # None if skipped

    def _goto_next_session(self):
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

    def save_logs_dialog(self):
        """Combine today's daily log and current task log (if set) into a single markdown and let user save it."""
        ts_day = now().strftime("%Y-%m-%d")
        daily_path = LOG_DIR / f"Pomodoro_{ts_day}.md"
        task_name = self.task_var.get().strip()
        combined = []

        if daily_path.exists():
            combined.append(daily_path.read_text(encoding="utf-8"))

        if task_name:
            tname = sanitize_filename(task_name) + ".md"
            tpath = TASK_DIR / tname
            if tpath.exists():
                combined.append("\n\n# Task Rollup — " + task_name + "\n\n")
                combined.append(tpath.read_text(encoding="utf-8"))

        if not combined:
            messagebox.showinfo("Save Logs", "No logs to save yet.")
            return

        default_name = f"Pomodoro_Export_{ts_day}.md"
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("All Files", "*.*")],
            initialfile=default_name,
            title="Save Logs As…"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(combined))
            messagebox.showinfo("Save Logs", f"Saved logs to:\n{path}")
        except Exception as e:
            messagebox.showerror("Save Logs", f"Failed to save logs:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PomodoroApp(root)
    root.mainloop()
