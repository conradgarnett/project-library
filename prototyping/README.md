# Prototyping (v1)

Early iterations of the terminal, kept for reference. **Not used by the current
Delta Terminal** (which is `server.py` + `static/delta/` + the Electron app in
`bloomberg-app/`).

| File | What it was |
|------|-------------|
| `main.py` | First keyless web version (launched by `run.sh`) |
| `bloomberg_v2.py` | Textual TUI version |
| `terminal.py` | Earlier Textual TUI version |
| `desktop.py` | pywebview desktop app (pre-Electron) |
| `build.py` | Packaged `desktop.py` into a .app (replaced by electron-builder) |
| `run.sh` | Launcher for `main.py` |
| `bloomberg.css` | Styles for the old web version |
