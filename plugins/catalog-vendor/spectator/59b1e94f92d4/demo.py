#!/usr/bin/env python3
"""C6 Demo script — Spectator Mode end-to-end, timed with assertions.

Flow (measured, target ≤180s):
  1. Start standalone server (serve.py) in background.
  2. Host: get /status (401 without bearer).
  3. Host: extract bearer token from host_secret file.
  4. Host: mint invite.
  5. Guest: join via POST /invites/join (BODY token).
  6. Guest: poll /feed (cursor 0).
  7. Guest: submit suggestion.
  8. Host: list suggestions → confirm pending.
  9. Host: approve suggestion.
 10. Guest: poll /feed → confirm suggestion status changed (or list own).
 11. Host: revoke invite.
 12. Guest: poll /feed → confirm 403 (revoked).
 13. Shutdown server.

Run twice:
  A) Fresh DB (no prior state).
  B) Stale DB (re-use the DB from run A, simulate dead-session revival).

Assertions: every HTTP response status is as expected; JSON payloads contain
required keys; total elapsed < 180s.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Config — resolved from this checkout
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"
SRC_DIR = REPO_ROOT / "src"
DATA_DIR = Path(
    os.environ.get(
        "SPECTATOR_DEMO_DATA_DIR",
        str(Path(tempfile.gettempdir()) / f"spectator-demo-{os.getpid()}"),
    )
)
BASE_URL = "http://127.0.0.1:8788/api/plugins/spectator"
TIMEOUT_S = 30


def _clean_data_dir() -> None:
    import shutil
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _start_server() -> subprocess.Popen:
    env = {
        **os.environ,
        "PYTHONPATH": f"{SRC_DIR}:{DASHBOARD_DIR}",
        "SPECTATOR_DATA_DIR": str(DATA_DIR),
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "spectator.serve"],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for health
    for _ in range(20):
        try:
            r = httpx.get(f"{BASE_URL}/guest.html", timeout=1)
            if r.status_code == 200:
                break
        except httpx.ConnectError:
            pass
        time.sleep(0.25)
    return proc


def _stop_server(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _host_bearer() -> str:
    secret_path = DATA_DIR / "host_secret"
    for _ in range(30):
        if secret_path.exists():
            return secret_path.read_bytes().hex()
        time.sleep(0.1)
    raise RuntimeError("host_secret never appeared")


def _assert_status(resp: httpx.Response, expected: int, ctx: str) -> None:
    assert resp.status_code == expected, (
        f"{ctx}: expected {expected}, got {resp.status_code}: {resp.text[:200]}"
    )


def _assert_json_keys(body: dict, required: set, ctx: str) -> None:
    missing = required - set(body.keys())
    assert not missing, f"{ctx}: missing keys {missing} in {body}"


# ---------------------------------------------------------------------------
# Demo flow
# ---------------------------------------------------------------------------

def run_demo(stale: bool = False) -> float:
    label = "STALE" if stale else "FRESH"
    print(f"\n=== Demo run ({label}) ===")
    if not stale:
        _clean_data_dir()
    # Ensure data dir exists for stale run
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    proc = _start_server()
    try:
        start = time.time()

        # 1. Guest.html loads without auth
        r = httpx.get(f"{BASE_URL}/guest.html", timeout=TIMEOUT_S)
        _assert_status(r, 200, "guest.html load")
        assert "Spectator Mode" in r.text, "guest.html missing title"
        print("  [1/12] guest.html loads OK")

        # 2. /status without bearer → 401
        r = httpx.get(f"{BASE_URL}/status", timeout=TIMEOUT_S)
        _assert_status(r, 401, "status without auth")
        print("  [2/12] /status 401 OK")

        # 3. Host bearer
        bearer = _host_bearer()
        host_hdr = {"Authorization": f"Bearer {bearer}"}
        print("  [3/12] host bearer acquired")

        # 4. /status with bearer → 200
        r = httpx.get(f"{BASE_URL}/status", headers=host_hdr, timeout=TIMEOUT_S)
        _assert_status(r, 200, "status with auth")
        body = r.json()
        _assert_json_keys(body, {"session_id", "host_active", "guest_count", "pending_suggestions", "uptime_seconds", "feed_source"}, "status response")
        print(f"  [4/12] /status 200 OK (feed_source={body['feed_source']})")

        # 5. Mint invite
        r = httpx.post(f"{BASE_URL}/invites", headers=host_hdr, json={"session_label": "demo", "ttl_seconds": 300}, timeout=TIMEOUT_S)
        _assert_status(r, 200, "mint invite")
        invite = r.json()
        _assert_json_keys(invite, {"invite_id", "token", "token_hash_prefix", "expires_at"}, "mint invite response")
        invite_token = invite["token"]
        print(f"  [5/12] invite minted (id={invite['invite_id'][:8]})")

        # 6. Guest joins
        r = httpx.post(f"{BASE_URL}/invites/join", json={"token": invite_token, "name": "Demo Guest"}, timeout=TIMEOUT_S)
        _assert_status(r, 200, "join invite")
        guest = r.json()
        _assert_json_keys(guest, {"guest_id", "guest_token", "session_id", "feed_cursor"}, "join response")
        guest_token = guest["guest_token"]
        guest_hdr = {"Authorization": f"Bearer {guest_token}"}
        print(f"  [6/12] guest joined (id={guest['guest_id'][:8]})")

        # 7. Guest polls feed
        r = httpx.get(f"{BASE_URL}/feed?since=0&limit=10", headers=guest_hdr, timeout=TIMEOUT_S)
        _assert_status(r, 200, "guest feed poll")
        feed = r.json()
        _assert_json_keys(feed, {"events", "reset"}, "feed response")
        print(f"  [7/12] guest feed polled ({len(feed['events'])} events)")

        # 8. Guest submits suggestion
        r = httpx.post(f"{BASE_URL}/suggestions", headers=guest_hdr, json={"content": "This is a demo suggestion from the guest.", "role": "user"}, timeout=TIMEOUT_S)
        _assert_status(r, 200, "submit suggestion")
        sug = r.json()
        _assert_json_keys(sug, {"suggestion_id", "status", "receipt"}, "suggestion submit response")
        assert sug["status"] == "pending", f"suggestion status should be pending, got {sug['status']}"
        print(f"  [8/12] suggestion submitted (id={sug['suggestion_id'][:8]})")

        # 9. Host lists suggestions
        r = httpx.get(f"{BASE_URL}/suggestions?status=pending", headers=host_hdr, timeout=TIMEOUT_S)
        _assert_status(r, 200, "host list suggestions")
        listing = r.json()
        _assert_json_keys(listing, {"items", "total"}, "suggestion list response")
        assert listing["total"] >= 1, "expected at least one suggestion"
        suggestion_id = listing["items"][0]["id"]
        print(f"  [9/12] host listed {listing['total']} suggestion(s)")

        # 10. Host approves
        r = httpx.post(f"{BASE_URL}/suggestions/{suggestion_id}/approve", headers=host_hdr, timeout=TIMEOUT_S)
        _assert_status(r, 200, "approve suggestion")
        approved = r.json()
        _assert_json_keys(approved, {"suggestion_id", "status"}, "approve response")
        # In standalone mode (no host desktop session) injection is "unreachable";
        # status is still "approved" and the guest can observe that.
        assert approved["status"] == "approved", f"expected approved, got {approved['status']}"
        print(f"  [10/12] suggestion approved (receipt={approved.get('receipt')}, injected={approved.get('injected')})")

        # 11. Guest sees updated status (poll own suggestions)
        r = httpx.get(f"{BASE_URL}/suggestions", headers=guest_hdr, timeout=TIMEOUT_S)
        _assert_status(r, 200, "guest list own suggestions")
        guest_listing = r.json()
        assert guest_listing["total"] >= 1, "guest should see own suggestion"
        own = next((i for i in guest_listing["items"] if i["id"] == suggestion_id), None)
        assert own is not None, "guest should see the approved suggestion"
        assert own["status"] == "approved", f"guest view should show approved, got {own['status']}"
        print("  [11/12] guest sees approved status")

        # 12. Host revokes invite
        r = httpx.delete(f"{BASE_URL}/invites/{invite['invite_id']}", headers=host_hdr, timeout=TIMEOUT_S)
        _assert_status(r, 200, "revoke invite")
        revoked = r.json()
        _assert_json_keys(revoked, {"status", "invite_id"}, "revoke response")
        print("  [12/12] invite revoked")

        # 13. Guest feed → 410 after revocation (revoked, not merely forbidden)
        time.sleep(2.5)
        r = httpx.get(f"{BASE_URL}/feed?since=0&limit=10", headers=guest_hdr, timeout=TIMEOUT_S)
        _assert_status(r, 410, "guest feed after revoke")
        print("  [+] guest feed 410 after revoke (OK)")

        elapsed = time.time() - start
        print(f"\n  Elapsed: {elapsed:.1f}s")
        return elapsed
    finally:
        _stop_server(proc)


def main() -> int:
    print("Spectator Mode C6 Demo")
    print("Target: complete under 180s per run")
    total = 0.0

    # Run A — fresh DB
    elapsed_a = run_demo(stale=False)
    total += elapsed_a
    assert elapsed_a < 180.0, f"FRESH run exceeded 180s: {elapsed_a:.1f}s"

    # Run B — stale DB (same directory, server restart)
    elapsed_b = run_demo(stale=True)
    total += elapsed_b
    assert elapsed_b < 180.0, f"STALE run exceeded 180s: {elapsed_b:.1f}s"

    print(f"\n=== TOTAL elapsed: {total:.1f}s (A={elapsed_a:.1f}s, B={elapsed_b:.1f}s) ===")
    assert total < 360.0, f"Combined runs exceeded 360s: {total:.1f}s"
    print("All assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
