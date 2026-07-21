import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "resources", "lib"))

from urllib.parse import parse_qs  # noqa: E402
from kodi.router import route_movie, parse_argv  # noqa: E402

if __name__ == "__main__":
    handle, params = parse_argv(sys.argv)
    route_movie(handle, params.get("action", ""), params)
