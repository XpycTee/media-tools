import os
import threading
import webbrowser

from app import create_app
from app.runtime import get_app_mode, get_bind_host, get_server_port, get_start_url


if __name__ == "__main__":
    app = create_app()
    host = get_bind_host()
    port = get_server_port()
    start_url = get_start_url(host, port)

    # Prevent double-open when Flask reloader is enabled.
    if (
        get_app_mode() == "browser"
        and (os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug)
    ):
        threading.Timer(0.8, lambda: webbrowser.open(start_url)).start()

    app.run(host=host, port=port)
