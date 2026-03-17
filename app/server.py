import threading
import time
from contextlib import suppress
from urllib.request import Request, urlopen

from werkzeug.serving import make_server


class EmbeddedServer:
    def __init__(self, app, host, port):
        self.host = host
        self.port = port
        self._server = make_server(host, port, app, threaded=True)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self):
        self._thread.start()

    def wait_until_ready(self, timeout=10.0):
        end_time = time.time() + timeout
        probe_url = f"http://{self.host}:{self.port}/"
        while time.time() < end_time:
            try:
                req = Request(probe_url, method="GET")
                with urlopen(req, timeout=0.5):
                    return True
            except Exception:
                time.sleep(0.1)
        return False

    def shutdown(self):
        with suppress(Exception):
            self._server.shutdown()
        with suppress(Exception):
            self._server.server_close()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)
