#!/usr/bin/env python3
"""
Open Bloomberg Terminal — Desktop App
Runs as a standalone native window. No browser required.

Run:      python desktop.py
Build:    python build.py   →  dist/Bloomberg Terminal.app
"""

import sys
import time
import threading
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8000
URL  = f"http://{HOST}:{PORT}"

# Add bloomberg dir to path so server.py imports feeds/
sys.path.insert(0, str(Path(__file__).parent))


def start_server():
    import uvicorn
    uvicorn.run("server:app", host=HOST, port=PORT, log_level="error")


def wait_for_server(timeout=20):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{URL}/api/status", timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def main():
    # Start backend in background thread
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    if not wait_for_server():
        print("Backend failed to start.")
        sys.exit(1)

    # Open native window (no browser, no address bar)
    import webview
    window = webview.create_window(
        title="Bloomberg Terminal",
        url=URL,
        width=1600,
        height=960,
        min_size=(1200, 700),
        background_color="#0a0e1a",
        frameless=False,
        easy_drag=False,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
