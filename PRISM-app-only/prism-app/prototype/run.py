#!/usr/bin/env python3
"""PRISM prototype launcher — cross-platform, no git required.

    python run.py          (or: python3 run.py)

What it does, in order:
  1. checks the Python version
  2. creates a private .venv next to this file if one does not exist
  3. installs flask into that venv if it is missing
  4. finds a free port starting at 8000
  5. starts the app and opens your browser

It never installs anything into your system Python, so it cannot break another
project and does not trip the "externally-managed-environment" error that
Debian and Ubuntu raise for a bare `pip install`.

Flags:
  --port N     start on a specific port
  --no-open    do not open a browser
  --check      verify the install only, then exit (no server)
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import venv

HERE = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(HERE, ".venv")
MIN_PY = (3, 10)


def venv_python() -> str:
    if os.name == "nt":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python3")


def running_in_our_venv() -> bool:
    return os.path.abspath(sys.prefix) == os.path.abspath(VENV_DIR)


def has_flask(python: str) -> bool:
    try:
        return subprocess.run(
            [python, "-c", "import flask"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode == 0
    except OSError:
        return False


def free_port(start: int) -> int:
    for port in range(start, start + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit("No free port found between %d and %d." % (start, start + 40))


def main() -> None:
    args = sys.argv[1:]
    want_port = None
    if "--port" in args:
        want_port = int(args[args.index("--port") + 1])
    no_open = "--no-open" in args
    check_only = "--check" in args

    if sys.version_info < MIN_PY:
        raise SystemExit(
            "PRISM needs Python %d.%d or newer. This is %s.\n"
            "Download a current Python from https://python.org/downloads"
            % (MIN_PY[0], MIN_PY[1], sys.version.split()[0])
        )

    # --- 1. make sure we are the interpreter that has flask ------------------
    if not running_in_our_venv():
        target = venv_python()
        if not os.path.exists(target):
            print("First run: creating an isolated environment in .venv ...", flush=True)
            venv.EnvBuilder(with_pip=True, clear=False).create(VENV_DIR)
            if not os.path.exists(target):
                raise SystemExit("Could not create .venv. Check that you can write to this folder.")
        if not has_flask(target):
            print("Installing flask into .venv (about 10 seconds, one time only) ...", flush=True)
            r = subprocess.run([target, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
            r = subprocess.run([target, "-m", "pip", "install", "--quiet", "flask"])
            if r.returncode != 0:
                raise SystemExit(
                    "Could not install flask. If you are offline, connect once and rerun.\n"
                    "Behind a proxy: set HTTPS_PROXY, or run\n"
                    "  %s -m pip install flask" % target
                )
        print("Re-launching inside .venv ...", flush=True)
        os.execv(target, [target, os.path.abspath(__file__)] + args)

    # --- 2. we are inside the venv and flask is present ---------------------
    import flask  # noqa: F401

    from importlib.metadata import PackageNotFoundError, version
    try:
        flask_version = version("flask")
    except PackageNotFoundError:
        flask_version = "unknown"

    print("Python  %s" % sys.version.split()[0], flush=True)
    print("Flask   %s" % flask_version, flush=True)
    print("Engine  %s" % os.path.normpath(os.path.join(HERE, "..", "prism", "pipeline.py")), flush=True)

    if check_only:
        print("\nInstall check passed. Start the app with:  python run.py", flush=True)
        return

    default_port = int(os.environ.get("PORT", "8000"))
    if want_port:
        port = want_port
    else:
        port = free_port(default_port)
        if port != default_port:
            print("Port %d is busy, using %d instead." % (default_port, port), flush=True)

    env = dict(os.environ, PORT=str(port), PRISM_NO_OPEN="1")
    print("\nStarting PRISM on http://localhost:%d   (Ctrl+C to stop)\n" % port, flush=True)

    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py")], env=env)
    try:
        if not no_open:
            for _ in range(40):
                time.sleep(0.25)
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    if s.connect_ex(("127.0.0.1", port)) == 0:
                        import webbrowser
                        webbrowser.open("http://localhost:%d/" % port)
                        break
        proc.wait()
    except KeyboardInterrupt:
        print("\nStopping.")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
