import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import time
import json
import os
from datetime import datetime, date

APP_NAME = "Pomodoro + Memo Pad"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def human_time(seconds:int)->str:
    m, s = divmod(max(0,int(seconds)), 60)
    return f"{m:02}:{s:02}"

class PomodoroApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("420x420")
        self.resizable(False, False)

        # State
        self.mode = tk.StringVar(value="Work")  # Work | Short | Long
        self.work_min = tk.IntVar(value=25)
        self.short_min = tk.IntVar(value=5)
        self.long_min = tk.IntVar(value=15)
        self.cycles_before_long = tk.IntVar(value=4)
        self.auto_start = tk.BooleanVar(value=True)

        self.task_title = tk.StringVar(value="My Study Task")
        self.running = False
        self.remaining = self.work_min.get() * 60
        self.cycle_count = 0
        self._timer_after_id = None

        # UI
        self._build_ui()
        self._update_time_label()
        self._update_status()

    def _build_ui(self):
        pad = 8

        top = ttk.Frame(self, padding=pad)
        top.pack(fill="x")
        ttk.Label(top, text="Task Title:").pack(side="left")
        ttk.Entry(top, textvariable=self.task_title, width=28).pack(side="left", padx=(4,0))
        ttk.Button(top, text="Open Task Log", command=self.open_task_log).pack(side="right", padx=(6,0))
        ttk.Button(top, text="Export Log", command=self.export_log).pack(side="right")

        header = ttk.Frame(self, padding=pad)
        header.pack(fill="x")
        ttk.Label(header, text="Mode:").pack(side="left")
        for m in ("Work","Short","Long"):
            ttk.Radiobutton(header, text=m, value=m, variable=self.mode, command=self.on_mode_change).pack(side="left", padx=2)

        center = ttk.Frame(self, padding=pad)
        center.pack(fill="both", expand=True)

        self.time_label = ttk.Label(center, text="25:00", font=("Segoe UI", 48, "bold"), anchor="center")
        self.time_label.pack(pady=(18,8), fill="x")

        self.status_label = ttk.Label(center, text="Paused • Cycle 0", anchor="center")
        self.status_label.pack()

        controls = ttk.Frame(center)
        controls.pack(pady=6)
        self.start_btn = ttk.Button(controls, text="Start", command=self.toggle_start)
        self.start_btn.grid(row=0, column=0, padx=4)
        ttk.Button(controls, text="Skip", command=self.skip).grid(row=0, column=1, padx=4)
        ttk.Button(controls, text="Reset", command=self.reset).grid(row=0, column=2, padx=4)

        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(fill="x", pady=(2,4))

        settings = ttk.LabelFrame(self, text="Settings", padding=pad)
        settings.pack(fill="x", padx=pad, pady=(0, pad))

        row = 0
        ttk.Label(settings, text="Work (min)").grid(row=row, column=0, sticky="w", padx=4, pady=2)
        ttk.Spinbox(settings, from_=1, to=300, textvariable=self.work_min, width=5, command=self.apply_duration).grid(row=row, column=1, padx=4, pady=2)
        row += 1
        ttk.Label(settings, text="Short Break (min)").grid(row=row, column=0, sticky="w", padx=4, pady=2)
        ttk.Spinbox(settings, from_=1, to=300, textvariable=self.short_min, width=5, command=self.apply_duration).grid(row=row, column=1, padx=4, pady=2)
        row += 1
        ttk.Label(settings, text="Long Break (min)").grid(row=row, column=0, sticky="w", padx=4, pady=2)
        ttk.Spinbox(settings, from_=1, to=300, textvariable=self.long_min, width=5, command=self.apply_duration).grid(row=row, column=1, padx=4, pady=2)
        row += 1
        ttk.Label(settings, text="Cycles before long break").grid(row=row, column=0, sticky="w", padx=4, pady=2)
        ttk.Spinbox(settings, from_=1, to=50, textvariable=self.cycles_before_long, width=5).grid(row=row, column=1, padx=4, pady=2)
        row += 1
        ttk.Checkbutton(settings, text="Auto-start next session", variable=self.auto_start).grid(row=row, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        # Current log preview
        self.log_preview = tk.Text(self, height=7, wrap="word")
        self.log_preview.pack(fill="both", expand=False, padx=pad, pady=(0,pad))
        self.log_preview.insert("end", "Memos preview will appear here after each Work session.\n")
        self.log_preview.config(state="disabled")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # Timer mechanics
    def start(self):
        if not self.running:
            self.running = True
            self.start_btn.config(text="Pause")
            self._tick()

    def pause(self):
        if self.running:
            self.running = False
            self.start_btn.config(text="Start")
            if self._timer_after_id:
                self.after_cancel(self._timer_after_id)
                self._timer_after_id = None
        self._update_status()

    def toggle_start(self):
        if self.running: self.pause()
        else: self.start()

    def reset(self):
        self.pause()
        self.cycle_count = 0
        self.apply_duration()
        self._update_status()

    def skip(self):
        self.pause()
        self.next_session()

    def apply_duration(self):
        minutes = self._default_minutes_for_mode(self.mode.get())
        self.remaining = minutes * 60
        self._update_time_label()
        self._update_status()

    def on_mode_change(self):
        self.apply_duration()

    def _default_minutes_for_mode(self, mode):
        return {"Work": self.work_min.get(),
                "Short": self.short_min.get(),
                "Long": self.long_min.get()}.get(mode, self.work_min.get())

    def _tick(self):
        if not self.running:
            return
        if self.remaining <= 0:
            self.pause()
            self.session_finished()
            return
        self.remaining -= 1
        self._update_time_label()
        self._update_status()
        self._timer_after_id = self.after(1000, self._tick)

    def _update_time_label(self):
        self.time_label.config(text=human_time(self.remaining))

    def _update_status(self):
        state = "Running" if self.running else "Paused"
        self.status_label.config(text=f"{self.mode.get()} • {state} • Cycle {self.cycle_count}")

    # Session transitions & memos
    def session_finished(self):
        # If a Work session ended, ask for a memo
        finished_mode = self.mode.get()
        if finished_mode == "Work":
            self.cycle_count += 1
            self.show_memo_window()
            # Decide next: short or long
            if self.cycle_count % max(1, self.cycles_before_long.get()) == 0:
                self.mode.set("Long")
            else:
                self.mode.set("Short")
        else:
            # From a break, back to Work
            self.mode.set("Work")

        self.apply_duration()
        if self.auto_start.get():
            self.start()

    def show_memo_window(self):
        win = tk.Toplevel(self)
        win.title("Quick Memo (what did you study?)")
        win.geometry("420x260")
        ttk.Label(win, text="Add a quick memo for this Work session:").pack(anchor="w", padx=10, pady=(10,4))
        memo = tk.Text(win, height=8, wrap="word")
        memo.pack(fill="both", expand=True, padx=10, pady=4)

        # Pre-fill with time/context
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        preset = f"[{timestamp}] "
        memo.insert("end", preset)

        btns = ttk.Frame(win)
        btns.pack(fill="x", pady=8)
        def save_and_close():
            content = memo.get("1.0","end").strip()
            if content and content != preset.strip():
                self.save_memo(content)
            self.refresh_log_preview()
            win.destroy()
        ttk.Button(btns, text="Save", command=save_and_close).pack(side="right", padx=8)
        ttk.Button(btns, text="Skip", command=lambda: (win.destroy())).pack(side="right")

        memo.focus_set()

    # Data persistence
    def _log_path_for_today(self):
        # One JSONL per task title per day
        safe_task = "".join(c for c in self.task_title.get() if c.isalnum() or c in (" ","-","_")).strip().replace(" ","_")
        if not safe_task: safe_task = "Task"
        fname = f"{date.today().isoformat()}_{safe_task}.jsonl"
        return os.path.join(DATA_DIR, fname)

    def save_memo(self, text):
        rec = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "cycle": self.cycle_count,
            "mode": "Work",
            "task_title": self.task_title.get(),
            "memo": text
        }
        with open(self._log_path_for_today(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def read_all_memos(self):
        path = self._log_path_for_today()
        memos = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        memos.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return memos

    def refresh_log_preview(self):
        memos = self.read_all_memos()
        self.log_preview.config(state="normal")
        self.log_preview.delete("1.0","end")
        if not memos:
            self.log_preview.insert("end", "No memos yet for today's task.\n")
        else:
            self.log_preview.insert("end", f"Task: {self.task_title.get()} • {date.today().isoformat()}\n")
            self.log_preview.insert("end", "-"*40 + "\n")
            for m in memos:
                ts = m.get("timestamp","")[:16].replace("T"," ")
                cyc = m.get("cycle","?")
                self.log_preview.insert("end", f"[{ts}] (Cycle {cyc})\n{m.get('memo','').strip()}\n\n")
        self.log_preview.config(state="disabled")

    def open_task_log(self):
        # Open the JSONL file in default app (Notepad). If empty, show info.
        path = self._log_path_for_today()
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("Error", f"Couldn't open log file:\n{e}")

    def export_log(self):
        # Export today's task memos to Markdown
        memos = self.read_all_memos()
        if not memos:
            messagebox.showinfo("Export", "No memos to export yet.")
            return
        default_name = f"{date.today().isoformat()}_{self.task_title.get().strip().replace(' ','_')}.md"
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            initialfile=default_name,
            filetypes=[("Markdown","*.md"),("Text","*.txt"),("All files","*.*")]
        )
        if not path: return
        lines = []
        lines.append(f"# Task Log: {self.task_title.get()}")
        lines.append(f"_Date: {date.today().isoformat()}_")
        lines.append("")
        for m in memos:
            ts = m.get("timestamp","")[:16].replace("T"," ")
            cyc = m.get("cycle","?")
            lines.append(f"## Cycle {cyc} — {ts}")
            lines.append("")
            lines.append(m.get("memo","").strip())
            lines.append("")
        try:
            with open(path,"w",encoding="utf-8") as f:
                f.write("\n".join(lines))
            messagebox.showinfo("Export", f"Exported to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export error", str(e))

    def on_close(self):
        self.pause()
        self.destroy()

if __name__ == "__main__":
    app = PomodoroApp()
    app.mainloop()