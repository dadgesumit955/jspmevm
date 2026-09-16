import io
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import server


def _ensure_schema():
    if not server.TURSO_ENABLED:
        return
    try:
        conn = server.get_conn()
        try:
            conn.execute("SELECT COUNT(*) FROM elections")
        finally:
            conn.close()
    except Exception:
        server.init_db()


if not server.TURSO_ENABLED:
    raise RuntimeError(
        "TURSO_URL/TURSO_TOKEN (or TURSO_DATABASE_URL/TURSO_AUTH_TOKEN) "
        "environment variables are required on Vercel."
    )

_ensure_schema()

_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


class _Headers(object):
    def __init__(self, environ):
        self._h = {}
        for key, value in environ.items():
            if key == "CONTENT_TYPE":
                self._h["content-type"] = value
            elif key == "CONTENT_LENGTH":
                self._h["content-length"] = value
            elif key.startswith("HTTP_"):
                self._h[key[5:].lower().replace("_", "-")] = value

    def get(self, key, default=None):
        return self._h.get(key.lower(), default)


def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO") or "/"
    qs = environ.get("QUERY_STRING")
    if qs:
        path = path + "?" + qs

    headers = _Headers(environ)
    try:
        length = int(headers.get("Content-Length") or "0")
    except ValueError:
        length = 0
    body = environ["wsgi.input"].read(length) if length else b""

    handler = server.Handler.__new__(server.Handler)
    handler.command = method
    handler.path = path
    handler.requestline = method + " " + path + " HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.headers = headers
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.close_connection = True

    do = getattr(handler, "do_" + method, None)
    if do is None and method == "HEAD":
        do = handler.do_GET
    if do is None:
        start_response(
            "405 Method Not Allowed",
            [("Allow", "GET, POST, PUT, DELETE, OPTIONS"), ("Content-Type", "text/plain; charset=utf-8")],
        )
        return [b"Method Not Allowed"]

    do()

    data = handler.wfile.getvalue()
    head, _, body_out = data.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n") if head else []
    status_line = lines[0].decode("latin-1", "replace") if lines else "HTTP/1.0 200 OK"
    parts = status_line.split(" ", 2)
    code = parts[1] if len(parts) > 1 else "200"
    message = parts[2] if len(parts) > 2 else ""
    out_headers = []
    for line in lines[1:]:
        name, _, value = line.partition(b":")
        name = name.decode("latin-1", "replace").strip()
        low = name.lower()
        if low in _HOP_BY_HOP or low in ("server", "date"):
            continue
        out_headers.append((name, value.decode("latin-1", "replace").strip()))
    start_response(code + (" " + message if message else ""), out_headers)
    return [body_out]