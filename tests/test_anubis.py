import hashlib
import json
from csfd import anubis

CHALLENGE = {
    "rules": {"algorithm": "fast", "difficulty": 1},
    "challenge": {"id": "test-id-123", "randomData": "deadbeefcafe", "difficulty": 1},
}
TRAP_HTML = (
    '<!doctype html><html><head><title>Ujišťujeme se, že nejste robot!</title>'
    '<script id="anubis_challenge" type="application/json">'
    + json.dumps(CHALLENGE) +
    '</script></head><body></body></html>'
)
REAL_HTML = "<html><body><h1>Matrix</h1></body></html>"


def test_is_trap_true_for_challenge_page():
    assert anubis.is_trap(TRAP_HTML) is True


def test_is_trap_false_for_real_page():
    assert anubis.is_trap(REAL_HTML) is False


def test_parse_challenge_extracts_fields():
    c = anubis.parse_challenge(TRAP_HTML)
    assert c == {"id": "test-id-123", "random_data": "deadbeefcafe", "difficulty": 1}


def test_solve_produces_hash_meeting_difficulty():
    h, nonce = anubis.solve("deadbeefcafe", 1)
    assert h[:1] == "0"
    assert hashlib.sha256(f"deadbeefcafe{nonce}".encode()).hexdigest() == h
    assert h[:1] == "0"


def test_solve_difficulty_two_needs_two_zeros():
    h, nonce = anubis.solve("abc", 2)
    assert h[:2] == "00"


def test_pass_challenge_url_has_all_params():
    url = anubis.pass_challenge_url(
        "https://www.csfd.cz", "id9", "0abc", 42, "https://www.csfd.cz/film/1/", 1000)
    assert url.startswith(
        "https://www.csfd.cz/.within.website/x/cmd/anubis/api/pass-challenge?")
    for frag in ["id=id9", "response=0abc", "nonce=42",
                 "redir=https%3A%2F%2Fwww.csfd.cz%2Ffilm%2F1%2F", "elapsedTime=1000"]:
        assert frag in url
