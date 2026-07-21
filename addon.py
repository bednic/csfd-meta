import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "resources", "lib"))

from urllib.parse import parse_qs  # noqa: E402
from kodi.router import route      # noqa: E402


def _parse_params(argv):
    # Kodi passes the action query on argv[1] (leading '?') and handle on argv[0]... varies;
    # metadata scrapers receive the request as a plugin path. Normalize both forms.
    handle = int(argv[1]) if len(argv) > 1 and argv[1].lstrip("-").isdigit() else -1
    query = ""
    for a in argv:
        if a.startswith("?") or "action=" in a:
            query = a.lstrip("?")
            break
    raw = parse_qs(query)
    params = {k: v[0] for k, v in raw.items()}
    return handle, params


if __name__ == "__main__":
    handle, params = _parse_params(sys.argv)
    action = params.get("action", "")
    route(handle, action, params)
