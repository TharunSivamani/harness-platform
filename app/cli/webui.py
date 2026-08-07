from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _frontend_dir() -> Path:
    return _repo_root() / "frontend"


def _wait_http(url: str, timeout: float = 90.0) -> bool:
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.4)
    return False


def _stream(prefix: str, pipe) -> None:
    try:
        for line in iter(pipe.readline, b""):
            if not line:
                break
            text = line.decode(errors="replace").rstrip()
            print(f"[{prefix}] {text}", flush=True)
    except Exception:  # noqa: BLE001
        pass


def cmd_ui(args) -> None:
    """
    Launch API + Next.js UI together (forge ui / forge --webui / forgeai ui).
    """
    root = _repo_root()
    frontend = _frontend_dir()
    if not frontend.is_dir():
        raise SystemExit(f"Frontend not found at {frontend}")

    api_host = getattr(args, "api_host", None) or "127.0.0.1"
    api_port = int(getattr(args, "api_port", None) or 8000)
    ui_host = getattr(args, "ui_host", None) or "127.0.0.1"
    ui_port = int(getattr(args, "ui_port", None) or 3000)
    open_browser = not getattr(args, "no_browser", False)
    install = not getattr(args, "no_install", False)

    api_url = f"http://{api_host}:{api_port}"
    ui_url = f"http://{ui_host}:{ui_port}"

    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm is required to launch the web UI. Install Node.js first.")

    if install and not (frontend / "node_modules").is_dir():
        print("Installing frontend dependencies (npm install)…", flush=True)
        subprocess.check_call([npm, "install"], cwd=str(frontend))

    env = os.environ.copy()
    env["NEXT_PUBLIC_API_URL"] = api_url
    # Windows-friendly process group handling
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    print(f"Starting API on {api_url}", flush=True)
    api_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            api_host,
            "--port",
            str(api_port),
        ],
        cwd=str(root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )

    print(f"Starting UI on {ui_url}", flush=True)
    ui_proc = subprocess.Popen(
        [npm, "run", "dev", "--", "-H", ui_host, "-p", str(ui_port)],
        cwd=str(frontend),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )

    threading.Thread(target=_stream, args=("api", api_proc.stdout), daemon=True).start()
    threading.Thread(target=_stream, args=("ui", ui_proc.stdout), daemon=True).start()

    def _shutdown(*_: object) -> None:
        for proc in (ui_proc, api_proc):
            if proc.poll() is not None:
                continue
            try:
                if sys.platform == "win32":
                    proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
                else:
                    proc.send_signal(signal.SIGTERM)
            except Exception:  # noqa: BLE001
                proc.terminate()
        for proc in (ui_proc, api_proc):
            try:
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                proc.kill()

    signal.signal(signal.SIGINT, lambda *_: (_shutdown(), sys.exit(0)))
    if hasattr(signal, "SIGTERM"):
        try:
            signal.signal(signal.SIGTERM, lambda *_: (_shutdown(), sys.exit(0)))
        except Exception:  # noqa: BLE001
            pass

    print("Waiting for services…", flush=True)
    api_ok = _wait_http(f"{api_url}/health", timeout=60)
    ui_ok = _wait_http(ui_url, timeout=90)
    if not api_ok:
        _shutdown()
        raise SystemExit("API failed to become healthy. Check [api] logs above.")
    if not ui_ok:
        print("UI did not respond in time; it may still be compiling.", flush=True)

    print(f"\nForgeAI Web UI → {ui_url}", flush=True)
    print(f"API docs         → {api_url}/docs", flush=True)
    print("LLM profiles: open Profiles in the UI (same data as `forge setup`).\n", flush=True)
    print("Press Ctrl+C to stop.\n", flush=True)

    if open_browser and ui_ok:
        try:
            webbrowser.open(ui_url)
        except Exception:  # noqa: BLE001
            pass

    try:
        while True:
            if api_proc.poll() is not None:
                _shutdown()
                raise SystemExit(f"API exited with code {api_proc.returncode}")
            if ui_proc.poll() is not None:
                _shutdown()
                raise SystemExit(f"UI exited with code {ui_proc.returncode}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping…", flush=True)
        _shutdown()
