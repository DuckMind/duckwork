"""Five argument shapes. No recorded session had an argument mistake."""
import json

from service import Deps, author_feed, profile_get

DID = "did:plc:AbCdef"


class Transport:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def __call__(self, url: str):
        self.urls.append(url)
        if "getAuthorFeed" in url:
            body = {"feed": []}
        else:
            body = {
                "did": "did:plc:z72i7hdynmk6r22z27h6tvur",
                "handle": "bsky.app",
                "displayName": "Bluesky",
                "followersCount": 1,
                "followsCount": 2,
                "postsCount": 3,
            }
        return 200, json.dumps(body).encode()


def call(args, tool="profile"):
    deps = Deps()
    transport = Transport()
    deps.transport = transport
    fn = author_feed if tool == "feed" else profile_get
    return fn(deps, args), transport


def test_handle_case_and_leading_at_are_the_same_account():
    out, transport = call({"actor": "@Bsky.App"})
    assert out["ok"] is True
    assert "actor=bsky.app" in transport.urls[-1]
    assert "Bsky" not in transport.urls[-1]


def test_fullwidth_digits_in_a_handle_are_sent_as_ascii():
    out, transport = call({"actor": "user１２.bsky.social"}, tool="feed")
    assert out["ok"] is True
    assert "actor=user12.bsky.social" in transport.urls[-1]
    assert "１２" not in transport.urls[-1]


def test_did_scheme_case_is_folded_and_the_identifier_case_stays():
    out, transport = call({"actor": "DID:PLC:AbCdef"})
    assert out["ok"] is True
    assert "actor=did%3Aplc%3AAbCdef" in transport.urls[-1]
    assert DID.split(":")[-1] in "AbCdef"


def test_extra_argument_names_the_fix_without_the_key():
    out, transport = call({"actor": "bsky.app", "limit": 50})
    text = json.dumps(out, ensure_ascii=False)
    assert out["ok"] is False
    assert out["error_type"] == "bad_args"
    assert "bsky.app" in out["message"]
    assert "limit" not in text
    assert "50" not in text
    assert transport.urls == []


def test_missing_and_numeric_actor_hide_the_input():
    missing, _transport = call({})
    numeric, transport = call({"actor": 10.0})
    text = json.dumps(numeric, ensure_ascii=False)
    assert missing["ok"] is False and missing["error_type"] == "bad_args"
    assert numeric["ok"] is False and numeric["error_type"] == "bad_args"
    assert "bsky.app" in missing["message"]
    assert "10.0" not in text
    assert "10" not in text
    assert transport.urls == []
