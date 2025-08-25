# Pomodoro Memo App (Windows, No .NET)

A lightweight **Pomodoro timer** with a built-in **memo pad** that pops up **after each work session** and **after each break**. 
All notes are saved as **Markdown** with rich session metadata (timestamps, durations, mode types).
No .NET required. You can bundle a **single .exe** using PyInstaller.

## Features
- Work / Short Break / Long Break timers (25 / 5 / 15 by default, fully editable).
- Auto-start next session (optional).
- **Memo dialog after each work session** to capture what you studied.
- **Break activity dialog** after each break to log what you did.
- Markdown logs saved by **date** and also grouped by **task** name.
- Simple **Do/Don't** suggestions derived from your break activity (keyword-based heuristic).
- Skip / Reset controls.
- Minimal dependencies (Python stdlib + Tkinter).

## Run (source)
1. Install Python 3.10+ (Windows).
2. From the `src` folder:
   ```bash
   python pomodoro.py
   ```

## Build a portable .exe (no Python needed on target)
1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Build from the project root:
   ```bash
   pyinstaller --noconfirm --onefile --windowed src/pomodoro.py
   ```
3. The executable will be at `dist/pomodoro.exe`.

## Where logs go
- Daily logs: `logs/Pomodoro_YYYY-MM-DD.md`
- Per-task logs: `logs/tasks/<TaskName>.md`

## Suggested Workflow
- Enter a **Task Name** at the top (e.g., “OS notes: CPU scheduling”).  
- Start your Pomodoro. When it ends, record a memo (what you studied).  
- During breaks, record what you did. The app creates a mini analysis (Do/Don't) for the next break cycle.
- Review daily or task logs in your editor/Obsidian/Notion (Markdown).