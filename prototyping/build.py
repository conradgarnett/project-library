#!/usr/bin/env python3
"""
Build Bloomberg Terminal into a standalone macOS .app
Run:  python build.py
"""

import subprocess, sys, shutil
from pathlib import Path

APP_NAME = "Bloomberg Terminal"
ROOT = Path(__file__).parent

# Check dependencies
for pkg in ["pywebview", "pyinstaller"]:
    try:
        __import__(pkg.replace("-","_").split(".")[0])
    except ImportError:
        print(f"Installing {pkg}…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

# Collect all data files PyInstaller needs to bundle
datas = [
    (str(ROOT / "static"),   "static"),
    (str(ROOT / "feeds"),    "feeds"),
]

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onedir",
    "--windowed",
    f"--name={APP_NAME}",
    "--hidden-import=uvicorn.logging",
    "--hidden-import=uvicorn.loops",
    "--hidden-import=uvicorn.loops.auto",
    "--hidden-import=uvicorn.protocols",
    "--hidden-import=uvicorn.protocols.http",
    "--hidden-import=uvicorn.protocols.http.auto",
    "--hidden-import=uvicorn.protocols.websockets",
    "--hidden-import=uvicorn.protocols.websockets.auto",
    "--hidden-import=uvicorn.lifespan",
    "--hidden-import=uvicorn.lifespan.on",
    "--hidden-import=engineio.async_drivers.aiohttp",
    "--hidden-import=webview.platforms.cocoa",   # macOS
    "--hidden-import=feeds",
    "--collect-all=webview",
]

for src, dst in datas:
    cmd += [f"--add-data={src}:{dst}"]

cmd.append(str(ROOT / "desktop.py"))

print(f"\nBuilding {APP_NAME}…")
subprocess.check_call(cmd)

app_path = ROOT / "dist" / f"{APP_NAME}.app"
if app_path.exists():
    print(f"\n✓ Built: {app_path}")
    print(f"  Drag to /Applications to install, or double-click to run.")
else:
    print("\n  Build complete. Check dist/ folder.")
