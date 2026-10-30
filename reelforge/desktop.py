"""Native window around ReelForge's authenticated loopback API."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import secrets
import socket
import sys
import threading
import time

from .runtime import configure_runtime, dispatch_tool


class DesktopSession:
    def __init__(self, data_dir=None, start_worker=True):
        from .app import create_app
        import uvicorn
        self.token = secrets.token_urlsafe(32)
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(128)
        self.url = f"http://127.0.0.1:{self.sock.getsockname()[1]}/#token={self.token}"
        self.app = create_app(data_dir=data_dir, token=self.token, start_worker=start_worker)
        self.server = uvicorn.Server(uvicorn.Config(self.app, log_config=None, access_log=False))
        self.thread = threading.Thread(target=lambda: self.server.run(sockets=[self.sock]), daemon=True)
        self.closed = False

    def start(self):
        self.thread.start()
        deadline = time.monotonic() + 20
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > deadline:
                self.close()
                raise RuntimeError("The local ReelForge service could not start. See desktop.log for details.")
            time.sleep(.05)
        return self

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.server.started and self.thread.is_alive():
            for job in self.app.state.store.rows():
                if job["state"] in {"queued", "running", "merging"}:
                    try:
                        self.app.state.engine.action(job["id"], "pause")
                    except ValueError:
                        pass
        self.server.should_exit = True
        if self.thread.is_alive():
            self.thread.join(timeout=12)
        if not self.thread.is_alive():
            self.sock.close()


def configure_logging():
    directory = Path(os.environ.get("REELFORGE_DATA_DIR", Path.home() / ".reelforge"))
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / "desktop.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True)


def main():
    if dispatch_tool(sys.argv[1:]):
        return
    configure_runtime()
    configure_logging()
    if "--bundled-self-test" in sys.argv[1:]:
        from .desktop_checks import bundled_tools_self_test
        bundled_tools_self_test()
        return
    if "--self-test" in sys.argv[1:]:
        import tempfile
        from urllib.request import Request, urlopen
        with tempfile.TemporaryDirectory() as directory:
            session = DesktopSession(Path(directory), start_worker=False)
            try:
                session.start()
                request = Request(session.url.split("#")[0] + "api/status", headers={"X-ReelForge-Token":session.token})
                with urlopen(request, timeout=10) as response:
                    assert response.status == 200
                if sys.stdout:
                    print("ReelForge desktop service self-test passed.")
            finally:
                session.close()
        return
    try:
        import webview
    except ImportError:
        raise SystemExit('Desktop support is missing. Run the desktop setup launcher or install ".[desktop]" first.') from None
    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["ALLOW_FILE_URLS"] = False
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    session = DesktopSession()
    try:
        session.start()
        window = webview.create_window("ReelForge", session.url, width=1380, height=960,
            min_size=(820, 650), background_color="#090b0a", text_select=True)
        def confirm_close():
            active = any(j["state"] in {"queued", "running", "merging"} for j in session.app.state.store.rows())
            if active:
                return window.create_confirmation_dialog("Close ReelForge?", "Downloads will stop and can be resumed when you reopen ReelForge.")
            return True
        window.events.closing += confirm_close
        icon = "ReelForge.icns" if sys.platform == "darwin" else "ReelForge.ico" if os.name == "nt" else "icon-256.png"
        kwargs = {"icon": str(Path(__file__).with_name("static") / icon)}
        webview.start(private_mode=False,
            storage_path=str(Path(os.environ.get("REELFORGE_DATA_DIR", Path.home() / ".reelforge")) / "desktop-webview"), **kwargs)
    except Exception:
        logging.exception("Desktop startup failed")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
