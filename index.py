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

handler = server.Handler