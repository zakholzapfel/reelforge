"""Loopback-only launcher. Session secret stays in the browser URL fragment."""
import argparse
import secrets
import socket
import threading
import webbrowser
import uvicorn
from .app import create_app
from .runtime import configure_runtime, dispatch_tool


def main():
    if dispatch_tool(__import__("sys").argv[1:]):
        return
    configure_runtime()
    parser = argparse.ArgumentParser(description="Launch ReelForge on this computer.")
    parser.add_argument("--port", type=int, default=0, help="Local port; default chooses a free port.")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("Port must be 0–65535.")
    sock = socket.socket()
    sock.bind(("127.0.0.1", args.port))
    sock.listen(128)
    port = sock.getsockname()[1]
    token = secrets.token_urlsafe(32)
    app = create_app(token=token)
    url = f"http://127.0.0.1:{port}/#token={token}"
    print(f"ReelForge is ready. Open this local session:\n{url}\nKeep this terminal open. Ctrl+C stops the app.")
    if not args.no_browser:
        threading.Timer(1, lambda: webbrowser.open(url)).start()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
