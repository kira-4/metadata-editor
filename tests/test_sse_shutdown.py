"""An open /api/events stream must not block shutdown (docker stop → SIGKILL)."""
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return socket.create_connection(("127.0.0.1", port), timeout=1)
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("server did not start")


def test_sigterm_with_open_sse_stream_exits_promptly(tmp_path):
    port = _free_port()
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
        "INCOMING_ROOT": str(tmp_path / "incoming"),
        "NAVIDROME_ROOT": str(tmp_path / "music"),
        "OPENROUTER_API_KEY": "",
    }
    (tmp_path / "incoming").mkdir()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        sock = _wait_for_port(port)
        time.sleep(0.5)  # lifespan startup
        sock.sendall(f"GET /api/events HTTP/1.1\r\nHost: localhost:{port}\r\n\r\n".encode())
        assert b"200" in sock.recv(1024)

        proc.send_signal(signal.SIGTERM)

        proc.wait(timeout=5)
        sock.close()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_scanner_stop_does_not_wait_out_the_scan_interval(monkeypatch):
    from app.config import config
    from app.scanner import FileScanner

    monkeypatch.setattr(config, "SCAN_INTERVAL_SECONDS", 30)
    scanner = FileScanner()
    monkeypatch.setattr(scanner, "scan_directory", lambda: [])
    monkeypatch.setattr(scanner, "purge_trash_if_due", lambda: None)
    scanner.start()
    time.sleep(0.2)  # now sleeping in the interval

    started = time.monotonic()
    scanner.stop()

    assert time.monotonic() - started < 1
    assert not scanner.thread.is_alive()
