import hashlib
import json
import re
from urllib.parse import urlencode

_CHALLENGE_RE = re.compile(
    r'<script[^>]*id="anubis_challenge"[^>]*>(.*?)</script>', re.S)
_TRAP_TITLE = "nejste robot"
_TRAP_EN = "not a bot"


class AnubisError(Exception):
    pass


def is_trap(html):
    if not html:
        return False
    low = html.lower()
    if 'id="anubis_challenge"' in low:
        return True
    return _TRAP_TITLE in low or _TRAP_EN in low


def parse_challenge(html):
    m = _CHALLENGE_RE.search(html)
    if not m:
        raise AnubisError("no anubis_challenge block found")
    try:
        blob = json.loads(m.group(1).strip())
        challenge = blob["challenge"]
        difficulty = blob.get("rules", {}).get("difficulty")
        if difficulty is None:
            difficulty = challenge["difficulty"]
        return {
            "id": challenge["id"],
            "random_data": challenge["randomData"],
            "difficulty": int(difficulty),
        }
    except (ValueError, KeyError) as e:
        raise AnubisError(f"malformed anubis challenge: {e}")


def solve(random_data, difficulty):
    prefix = "0" * difficulty
    nonce = 0
    while True:
        h = hashlib.sha256(f"{random_data}{nonce}".encode()).hexdigest()
        if h[:difficulty] == prefix:
            return h, nonce
        nonce += 1


def pass_challenge_url(base_url, challenge_id, response, nonce, redir, elapsed_ms=1000):
    qs = urlencode({
        "id": challenge_id, "response": response, "nonce": nonce,
        "redir": redir, "elapsedTime": elapsed_ms,
    })
    return f"{base_url}/.within.website/x/cmd/anubis/api/pass-challenge?{qs}"
