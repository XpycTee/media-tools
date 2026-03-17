import os
import sys

from app import create_app
from app.desktop_bridge import DesktopBridge
from app.runtime import get_bind_host, get_server_port, get_start_url
from app.server import EmbeddedServer


WINDOW_TITLE = "Media Tools"
WINDOW_SIZE = (1280, 900)
MIN_WINDOW_SIZE = (1024, 720)


def main():
    os.environ.setdefault("APP_MODE", "desktop")

    try:
        import webview
    except ImportError:
        print(
            "pywebview is not installed. Install dependencies with "
            "'pip install -r requirements.txt'.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    app = create_app()
    host = get_bind_host()
    port = get_server_port()
    start_url = get_start_url(host, port)
    server = EmbeddedServer(app, host, port)
    bridge = DesktopBridge(webview)

    server.start()
    if not server.wait_until_ready():
        server.shutdown()
        print(
            f"Failed to start backend server at {start_url}. "
            "Check APP_HOST/APP_PORT and try again.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    window = webview.create_window(
        WINDOW_TITLE,
        start_url,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=MIN_WINDOW_SIZE,
        js_api=bridge,
    )
    bridge.attach_window(window)

    try:
        webview.start(private_mode=False)
    finally:
        if window:
            server.shutdown()


if __name__ == "__main__":
    main()
