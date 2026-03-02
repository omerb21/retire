#!/usr/bin/env python3
"""
Safe Server Start Script - Ensures clean server startup
Kills any existing Python processes on port 8005 before starting
"""

import ctypes
import json
import msvcrt
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

SAFE_SERVER_START_VERSION = "2025-12-26.2"


def kill_port_processes(port=8005):
    """Kill all processes listening on the specified port"""
    print(f"🔍 Checking for processes on port {port}...")

    try:
        # Get all processes listening on port 8005
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=5
        )

        pids_to_kill = []
        for line in result.stdout.split("\n"):
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    pid = parts[-1]
                    if pid.isdigit():
                        pids_to_kill.append(int(pid))

        if pids_to_kill:
            print(
                f"⚠️  Found {len(pids_to_kill)} process(es) on port {port}: {pids_to_kill}"
            )

            for pid in pids_to_kill:
                try:
                    print(f"  🗑️  Killing PID {pid}...")
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/F", "/T"], timeout=5
                    )
                    print(f"  ✅ Killed PID {pid}")
                except Exception as e:
                    print(f"  ⚠️  Failed to kill PID {pid}: {e}")

            # Wait for ports to be released
            print("⏳ Waiting for port to be released...")
            time.sleep(3)

            # Verify port is free
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True, timeout=5
            )

            still_listening = False
            for line in result.stdout.split("\n"):
                if f":{port}" in line and "LISTENING" in line:
                    still_listening = True
                    break

            if still_listening:
                if not _is_admin():
                    print(
                        f"❌ Port {port} is still in use and this script is not running as Administrator. "
                        "Please run the server start script from an elevated terminal."
                    )
                    return False

                print(f"❌ Port {port} is still in use! Retrying...")
                time.sleep(2)
                return kill_port_processes(port)
            else:
                print(f"✅ Port {port} is now free!")
        else:
            print(f"✅ Port {port} is already free")

    except Exception as e:
        print(f"⚠️  Error checking port: {e}")
        return False

    return True


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _is_port_open(host: str, port: int, timeout_seconds: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except Exception:
        return False


def _get_listening_pids_from_netstat(port: int):
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return []

    pids = set()
    for line in (result.stdout or "").split("\n"):
        if f":{port}" not in line:
            continue
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if not parts:
            continue
        pid = parts[-1]
        if pid.isdigit():
            pids.add(int(pid))
    return sorted(pids)


def _try_graceful_taskkill_pids(pids, port: int) -> bool:
    if not pids:
        return True

    print(f"⚠️  Port {port} is in use. Attempting non-forced shutdown (no admin)...")
    for pid in pids:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid)],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            pass

    time.sleep(1)
    return not _is_port_open("127.0.0.1", port)


def _is_our_backend_running(port: int) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=0.8) as resp:
            raw = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return False
    except Exception:
        return False

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return False

    return (
        isinstance(payload, dict)
        and payload.get("status") == "ok"
        and ("version" in payload)
    )


def _acquire_single_instance_lock(project_root: str, port: int):
    lock_path = os.path.join(project_root, f".safe_server_start_{port}.lock")
    fh = open(lock_path, "a+")
    try:
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        fh.close()
        return None
    return fh


def start_server():
    """Start the Uvicorn server"""
    print("\n🚀 Starting Uvicorn server on port 8005...")
    print("=" * 60)

    try:
        reload_enabled = str(os.environ.get("RETIRE_BACKEND_RELOAD", "")).strip() == "1"
        args = [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8005",
        ]
        if reload_enabled:
            args.insert(4, "--reload")
        subprocess.run(
            args, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    except KeyboardInterrupt:
        print("\n\n⏹️  Server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 60)
    print("🛡️  SAFE SERVER START SCRIPT")
    print("=" * 60)
    print(f"SAFE_SERVER_START_VERSION={SAFE_SERVER_START_VERSION}")
    print(f"SCRIPT_PATH={os.path.abspath(__file__)}")

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lock_fh = _acquire_single_instance_lock(project_root, 8005)
    if lock_fh is None:
        print("⚠️  Another backend instance is already starting/running. Exiting.")
        sys.exit(0)

    if _is_port_open("127.0.0.1", 8005):
        print("ℹ️  Port 8005 is open. Probing /health...")
        if _is_our_backend_running(8005):
            print("✅ Backend is already running on port 8005. Nothing to do.")
            sys.exit(0)
        print("⚠️  /health probe did not match expected backend signature.")

    if _is_port_open("127.0.0.1", 8005) and not _is_admin():
        pids = _get_listening_pids_from_netstat(8005)
        ok = _try_graceful_taskkill_pids(pids, 8005)
        if not ok:
            print(
                "⚠️  Port 8005 is already in use, and this script is not running as Administrator. "
                "Please close the existing backend or run this script from an elevated terminal."
            )
            if pids:
                print(f"⚠️  Listening PIDs on 8005: {pids}")
            sys.exit(1)

    # Kill any existing processes on port 8005
    ok = kill_port_processes(8005)
    if not ok:
        sys.exit(1)

    # Start the server
    start_server()
