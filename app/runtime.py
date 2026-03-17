import os
import socket
import sys
from pathlib import Path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
DEFAULT_PAGE = "/video"


def get_app_mode():
    return os.environ.get("APP_MODE", "browser").strip().lower() or "browser"


def get_bind_host():
    return os.environ.get("APP_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST


def get_preferred_port():
    raw_port = os.environ.get("APP_PORT", "").strip()
    if not raw_port:
        return DEFAULT_PORT
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("APP_PORT must be an integer") from exc
    if not (0 <= port <= 65535):
        raise ValueError("APP_PORT must be between 0 and 65535")
    return port


def get_server_port():
    return choose_port(get_bind_host(), get_preferred_port())


def choose_port(host, preferred_port):
    if preferred_port == 0:
        return find_free_port(host)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, preferred_port))
        except OSError:
            return find_free_port(host)
    return preferred_port


def find_free_port(host):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def get_start_url(host, port, page=DEFAULT_PAGE):
    path = page if page.startswith("/") else f"/{page}"
    return f"http://{host}:{port}{path}"


def get_project_root():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def get_resource_path(*parts):
    return str(get_project_root().joinpath(*parts))
