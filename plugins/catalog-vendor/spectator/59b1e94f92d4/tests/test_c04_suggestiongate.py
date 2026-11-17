"""C4 tests — SuggestionGate + inject_message seam.

Acceptance criteria:
- Approve flip + inject are atomic; retry keeps SAME delivery_id; injected → 409.
- No auto-injection on any code path (test_no_auto_injection_e2e: queues checked).
- Pending suggestion never appears in session queue pre-approval.
- Rate-limit exceeded → rate_limited receipt; capacity → over_capacity.

Test plan:
- Unit: test_approve_atomicity, test_approve_recovery_semantics (both crash orders).
- Integration: test_inject_message_live_session (message in next turn, no interrupt).

The suggestion submit path reuses the agent_peer ReceiptState wire values verbatim
(queued|held|refused|unreachable|expired|invalid|rate_limited|over_capacity) plus
the plugin-specific ``host_gone``. The plugin does NOT import agent_peer (zero-dep);
the gate implements a self-contained rate limiter with identical burst/sustained
semantics (burst 5 / sustained 20 per minute per guest).
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spectator.auth.auth import HostSecretManager
from spectator.auth.invite import InviteManager
from spectator.db.db import SpectatorDB
from spectator.suggest.gate import ReceiptState, SuggestionError, SuggestionGate

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_data_dir(tmp_path):
    data_dir = tmp_path / "spectator"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def db(tmp_data_dir):
    database = SpectatorDB(tmp_data_dir / "spectator.db")
    database.init_schema()
    yield database
    database.close()


@pytest.fixture
def secret_mgr(tmp_data_dir):
    mgr = HostSecretManager(tmp_data_dir / "host_secret")
    assert mgr.load_or_create() is True
    return mgr


@pytest.fixture
def invite_mgr(db, secret_mgr):
    return InviteManager(db, secret_mgr, current_session_gen="gen-1")


@pytest.fixture
def joined_guest(invite_mgr):
    """Mint + join an invite, returning a real (guest_id, session_id) pair that
    satisfies the suggestions.guest_id FK."""
    mint = invite_mgr.mint_invite(session_id="test-session", session_gen="gen-1")
    join = invite_mgr.join_invite(mint["token"], guest_name="Guest")
    return {"guest_id": join["guest_id"], "guest_token": join["guest_token"],
            "session_id": join["session_id"]}


class FakeInjector:
    """Callable stand-in for the host inject_message seam."""

    def __init__(self, ok=True, block=False):
        self.ok = ok
        self.block = block
        self.calls = []

    def __call__(self, content, role="user", mode="queue"):
        self.calls.append({"content": content, "role": role, "mode": mode})
        if self.block:
            while True:
                time.sleep(0.05)
        return self.ok


@pytest.fixture
def injector():
    return FakeInjector(ok=True)


def make_gate(db, injector=None, **kwargs):
    return SuggestionGate(
        db,
        inject_fn=injector if injector is not None else FakeInjector(ok=True),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Unit: submission + receipts
# ---------------------------------------------------------------------------

class TestSubmit:
    def test_role_coercion(self, db, joined_guest, injector):
        gate = make_gate(db, injector)
        for role in ("system", "assistant", "tool", "user"):
            res = gate.submit(joined_guest["guest_id"], joined_guest["session_id"],
                              "hello", role=role)
            assert res["status"] == "pending"
            assert res["receipt"] == "held"
            row = db.conn.execute(
                "SELECT role FROM suggestions WHERE id = ?", (res["suggestion_id"],)
            ).fetchone()
            assert row["role"] == "user"

    def test_pending_receipt_is_held(self, db, joined_guest, injector):
        gate = make_gate(db, injector)
        res = gate.submit(joined_guest["guest_id"], joined_guest["session_id"], "hi")
        assert res["status"] == "pending"
        assert res["receipt"] == ReceiptState.HELD.value

    def test_empty_content_rejected(self, db, joined_guest, injector):
        gate = make_gate(db, injector)
        with pytest.raises(SuggestionError) as ei:
            gate.submit(joined_guest["guest_id"], joined_guest["session_id"], "   ")
        assert ei.value.status_code == 422
        assert ei.value.receipt_state == ReceiptState.INVALID.value

    def test_oversize_content_rejected(self, db, joined_guest, injector):
        gate = make_gate(db, injector)
        content = "x" * (32 * 1024 + 1)
        with pytest.raises(SuggestionError) as ei:
            gate.submit(joined_guest["guest_id"], joined_guest["session_id"], content)
        assert ei.value.status_code == 422
        assert ei.value.receipt_state == ReceiptState.INVALID.value

    def test_32kib_boundary_accepted(self, db, joined_guest, injector):
        gate = make_gate(db, injector)
        content = "x" * (32 * 1024)
        res = gate.submit(joined_guest["guest_id"], joined_guest["session_id"], content)
        assert res["status"] == "pending"


class TestRateLimit:
    def test_burst_sixth_rejected(self, db, joined_guest, injector):
        gate = make_gate(db, injector, capacity=1000)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        for i in range(5):
            res = gate.submit(gid, sid, f"msg {i}")
            assert res["status"] == "pending"
        with pytest.raises(SuggestionError) as ei:
            gate.submit(gid, sid, "msg 6")
        assert ei.value.status_code == 429
        assert ei.value.receipt_state == ReceiptState.RATE_LIMITED.value


class TestCapacity:
    def test_over_capacity(self, db, joined_guest, injector):
        gate = make_gate(db, injector, capacity=3, rate_burst=1000, rate_per_minute=1000)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        for i in range(3):
            res = gate.submit(gid, sid, f"msg {i}")
            assert res["status"] == "pending"
        with pytest.raises(SuggestionError) as ei:
            gate.submit(gid, sid, "msg overflow")
        assert ei.value.status_code == 503
        assert ei.value.receipt_state == ReceiptState.OVER_CAPACITY.value


# ---------------------------------------------------------------------------
# Unit: horizontal isolation
# ---------------------------------------------------------------------------

class TestIsolation:
    def test_guest_cannot_read_other_suggestion(self, db, joined_guest, injector, invite_mgr):
        gate = make_gate(db, injector)
        # Second guest via a second invite join
        mint2 = invite_mgr.mint_invite(session_id="test-session", session_gen="gen-1")
        join2 = invite_mgr.join_invite(mint2["token"], guest_name="Other")

        res_a = gate.submit(joined_guest["guest_id"], joined_guest["session_id"], "from A")
        # Guest B attempts to read Guest A's suggestion → 403
        with pytest.raises(SuggestionError) as ei:
            gate.get_suggestion(
                res_a["suggestion_id"], actor_role="guest",
                guest_id=join2["guest_id"], session_id="test-session",
            )
        assert ei.value.status_code == 403

    def test_guest_list_only_own(self, db, joined_guest, injector, invite_mgr):
        gate = make_gate(db, injector)
        mint2 = invite_mgr.mint_invite(session_id="test-session", session_gen="gen-1")
        join2 = invite_mgr.join_invite(mint2["token"], guest_name="Other")
        gate.submit(joined_guest["guest_id"], "test-session", "from A")
        gate.submit(join2["guest_id"], "test-session", "from B")

        lst = gate.list_suggestions("test-session", guest_id=join2["guest_id"])
        assert lst["total"] == 1
        assert all(item["guest_id"] == join2["guest_id"] for item in lst["items"])


# ---------------------------------------------------------------------------
# Unit: approve atomicity + idempotency + recovery
# ---------------------------------------------------------------------------

class TestApproveAtomicity:
    def test_inject_false_stays_approved_unreachable(self, db, joined_guest):
        gate = make_gate(db, FakeInjector(ok=False))
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "suggest")
        out = gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        assert out["injected"] is False
        assert out["status"] == "approved"
        assert out["receipt"] == ReceiptState.UNREACHABLE.value
        row = db.conn.execute(
            "SELECT status, delivery_state, delivery_id FROM suggestions WHERE id=?",
            (res["suggestion_id"],),
        ).fetchone()
        assert row["status"] == "approved"
        assert row["delivery_state"] == "unreachable"
        assert row["delivery_id"] is not None

    def test_inject_true_flips_injected_queued(self, db, joined_guest):
        gate = make_gate(db, FakeInjector(ok=True))
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "suggest")
        out = gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        assert out["injected"] is True
        assert out["status"] == "injected"
        assert out["receipt"] == ReceiptState.QUEUED.value

    def test_injected_then_approve_409(self, db, joined_guest):
        injector = FakeInjector(ok=True)
        gate = make_gate(db, injector)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "suggest")
        gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        with pytest.raises(SuggestionError) as ei:
            gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        assert ei.value.status_code == 409
        assert len(injector.calls) == 1

    def test_no_injection_on_submit(self, db, joined_guest):
        injector = FakeInjector(ok=True)
        gate = make_gate(db, injector)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        gate.submit(gid, sid, "suggest")
        assert injector.calls == []

    def test_delivery_id_minted_once_across_retries(self, db, joined_guest):
        injector = FakeInjector(ok=False)
        gate = make_gate(db, injector)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "suggest")
        first = gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        injector.ok = True
        second = gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        assert first["delivery_id"] == second["delivery_id"]
        assert second["injected"] is True

    def test_marker_prefixed_to_injected_content(self, db, joined_guest):
        injector = FakeInjector(ok=True)
        gate = make_gate(db, injector)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "check auth.py")
        out = gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        assert injector.calls[0]["content"] == f"[spectator:{out['delivery_id']}]\ncheck auth.py"
        assert injector.calls[0]["mode"] == "queue"
        assert injector.calls[0]["role"] == "user"


class TestApproveRecoverySemantics:
    def test_crash_order_a_inject_then_crash(self, db, joined_guest):
        """delivery_state=attempting after a crash → retry re-injects with the
        SAME delivery_id (no re-mint), then flips to injected."""
        gate = make_gate(db, FakeInjector(ok=True))
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "suggest")
        sid_ = res["suggestion_id"]

        # Simulate the crash window: status flipped + delivery_id minted +
        # delivery_state=attempting persisted, but the "injected" flip never ran.
        delivery_id = str(uuid.uuid4())
        with db.write_txn() as cur:
            cur.execute(
                "UPDATE suggestions SET status='approved', delivery_id=?, "
                "delivery_state='attempting' WHERE id=?",
                (delivery_id, sid_),
            )

        out = gate.approve(sid_, actor_role="host", session_id=sid)
        assert out["injected"] is True
        assert out["delivery_id"] == delivery_id

    def test_crash_order_b_crash_then_retry(self, db, joined_guest):
        """unreachable after a failed inject → retry re-injects with the SAME
        delivery_id and flips to injected."""
        injector = FakeInjector(ok=False)
        gate = make_gate(db, injector)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "suggest")
        first = gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        assert first["injected"] is False

        injector.ok = True
        second = gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        assert second["injected"] is True
        assert second["delivery_id"] == first["delivery_id"]


class TestInjectTimeout:
    def test_timeout_then_retry_same_delivery_id(self, db, joined_guest):
        """Timeout marks unreachable; a retry while the abandoned thread still
        runs is 409 (no double-inject); after it finishes, retry succeeds with
        the SAME delivery_id."""
        finished = threading.Event()

        def blocking_inject(content, role="user", mode="queue"):
            # Blocks longer than the 0.2s timeout, then completes.
            finished.wait(timeout=1.0)
            return True

        gate = make_gate(db, blocking_inject, inject_timeout_seconds=0.2)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "suggest")

        start = time.monotonic()
        out = gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        elapsed = time.monotonic() - start

        assert out["injected"] is False
        assert out["status"] == "approved"
        assert out["receipt"] == ReceiptState.UNREACHABLE.value
        assert out["reason"] == "timeout"
        assert elapsed < 2.0

        # Retry while the abandoned thread is still running → 409 (in-flight guard).
        with pytest.raises(SuggestionError) as ei:
            gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        assert ei.value.status_code == 409

        # Once the abandoned thread finishes and releases the guard, retry works
        # with the SAME delivery_id.
        finished.set()
        time.sleep(1.2)  # let the abandoned thread complete and release the guard
        good = FakeInjector(ok=True)
        gate.inject_fn = good
        retry = gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        assert retry["injected"] is True
        assert retry["delivery_id"] == out["delivery_id"]


# ---------------------------------------------------------------------------
# Unit: reject + expiry
# ---------------------------------------------------------------------------

class TestReject:
    def test_reject_pending(self, db, joined_guest, injector):
        gate = make_gate(db, injector)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "suggest")
        out = gate.reject(res["suggestion_id"], actor_role="host", session_id=sid)
        assert out["status"] == "rejected"
        assert out["receipt"] == ReceiptState.REFUSED.value

    def test_reject_approved_retract(self, db, joined_guest):
        gate = make_gate(db, FakeInjector(ok=False))
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "suggest")
        gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        out = gate.reject(res["suggestion_id"], actor_role="host", session_id=sid)
        assert out["status"] == "rejected"

    def test_reject_injected_409(self, db, joined_guest):
        gate = make_gate(db, FakeInjector(ok=True))
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "suggest")
        gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        with pytest.raises(SuggestionError) as ei:
            gate.reject(res["suggestion_id"], actor_role="host", session_id=sid)
        assert ei.value.status_code == 409


class TestExpiry:
    def _age_pending(self, db, suggestion_id):
        past = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
        with db.write_txn() as cur:
            cur.execute("UPDATE suggestions SET expires_at=? WHERE id=?", (past, suggestion_id))

    def test_lazy_expire_on_list(self, db, joined_guest, injector):
        gate = make_gate(db, injector, pending_ttl_seconds=60)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "stale")
        self._age_pending(db, res["suggestion_id"])
        lst = gate.list_suggestions(sid, guest_id=gid, status="pending")
        assert lst["total"] == 0
        row = db.conn.execute(
            "SELECT status, receipt_state FROM suggestions WHERE id=?", (res["suggestion_id"],)
        ).fetchone()
        assert row["status"] == "expired"
        assert row["receipt_state"] == ReceiptState.EXPIRED.value

    def test_lazy_expire_on_approve(self, db, joined_guest):
        gate = make_gate(db, FakeInjector(ok=True), pending_ttl_seconds=60)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "stale")
        self._age_pending(db, res["suggestion_id"])
        with pytest.raises(SuggestionError) as ei:
            gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        assert ei.value.status_code == 409
        assert ei.value.receipt_state == ReceiptState.EXPIRED.value

    def test_sweep_expired(self, db, joined_guest, injector):
        gate = make_gate(db, injector, pending_ttl_seconds=60)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        r1 = gate.submit(gid, sid, "stale")
        gate.submit(gid, sid, "fresh")
        self._age_pending(db, r1["suggestion_id"])
        swept = gate.sweep_expired(sid)
        assert swept == 1


# ---------------------------------------------------------------------------
# Integration: FastAPI endpoints
# ---------------------------------------------------------------------------

class TestEndpoints:
    def _make_client(self, tmp_data_dir, injector):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))
        from plugin_api import _state, init_plugin, router

        app = FastAPI()
        app.include_router(router, prefix="/api/plugins/spectator")
        init_plugin(data_dir=tmp_data_dir, session_id="test-feed-session")
        _state.suggest_gate.inject_fn = injector
        return TestClient(app), tmp_data_dir, _state

    def _host_token(self, tmp_data_dir):
        secret_path = tmp_data_dir / "host_secret"
        mgr = HostSecretManager(secret_path)
        mgr.load_or_create()
        return mgr.secret.hex()

    def _guest_token(self, _state):
        mint = _state.invite_mgr.mint_invite(
            session_id=_state.session_id, session_gen=_state.session_gen
        )
        join = _state.invite_mgr.join_invite(mint["token"], guest_name="Guest")
        return join["guest_token"], join["guest_id"]

    def test_submit_and_approve_end_to_end(self, tmp_data_dir):
        injector = FakeInjector(ok=True)
        client, data_dir, state = self._make_client(tmp_data_dir, injector)
        host_token = self._host_token(data_dir)
        guest_token, _ = self._guest_token(state)

        r = client.post(
            "/api/plugins/spectator/suggestions",
            json={"content": "check auth.py", "role": "assistant"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "pending"
        assert body["receipt"] == "held"

        # Pre-approval: nothing injected.
        assert injector.calls == []

        r2 = client.post(
            f"/api/plugins/spectator/suggestions/{body['suggestion_id']}/approve",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["injected"] is True
        assert injector.calls[0]["content"] == f"[spectator:{r2.json()['delivery_id']}]\ncheck auth.py"
        assert injector.calls[0]["mode"] == "queue"

    def test_no_auto_injection_e2e(self, tmp_data_dir):
        """A pending suggestion never reaches the inject seam until explicit approve."""
        injector = FakeInjector(ok=True)
        client, data_dir, state = self._make_client(tmp_data_dir, injector)
        guest_token, _ = self._guest_token(state)

        for i in range(3):
            r = client.post(
                "/api/plugins/spectator/suggestions",
                json={"content": f"pending {i}"},
                headers={"Authorization": f"Bearer {guest_token}"},
            )
            assert r.status_code == 200

        # Three pendings, zero injections — no auto-injection on any code path.
        assert injector.calls == []

    def test_inject_message_live_session_queue(self, tmp_data_dir):
        """Message appears in the next-turn queue (no interrupt): a session queue
        is only populated by approve, and mode is always queue."""
        session_queue = []
        def queueing_injector(content, role="user", mode="queue"):
            session_queue.append(content)
            return True

        client, data_dir, state = self._make_client(tmp_data_dir, queueing_injector)
        host_token = self._host_token(data_dir)
        guest_token, _ = self._guest_token(state)

        r = client.post(
            "/api/plugins/spectator/suggestions",
            json={"content": "live suggestion"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert session_queue == []

        client.post(
            f"/api/plugins/spectator/suggestions/{r.json()['suggestion_id']}/approve",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert len(session_queue) == 1
        assert session_queue[0].endswith("\nlive suggestion")
        assert session_queue[0].startswith("[spectator:")

    def test_guest_cannot_approve(self, tmp_data_dir):
        injector = FakeInjector(ok=True)
        client, data_dir, state = self._make_client(tmp_data_dir, injector)
        guest_token, _ = self._guest_token(state)
        r = client.post(
            "/api/plugins/spectator/suggestions",
            json={"content": "x"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        sid = r.json()["suggestion_id"]
        r2 = client.post(
            f"/api/plugins/spectator/suggestions/{sid}/approve",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert r2.status_code == 403

    def test_rate_limit_endpoint_429(self, tmp_data_dir):
        injector = FakeInjector(ok=True)
        client, data_dir, state = self._make_client(tmp_data_dir, injector)
        guest_token, _ = self._guest_token(state)
        for i in range(5):
            r = client.post(
                "/api/plugins/spectator/suggestions",
                json={"content": f"m{i}"},
                headers={"Authorization": f"Bearer {guest_token}"},
            )
            assert r.status_code == 200
        r = client.post(
            "/api/plugins/spectator/suggestions",
            json={"content": "m6"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert r.status_code == 429
        assert r.json()["detail"]["receipt_state"] == "rate_limited"


# ---------------------------------------------------------------------------
# Regression: Hermaguard Gate 0 findings
# ---------------------------------------------------------------------------

class TestGate0Regressions:
    """Locks in fixes for the HIGH/MEDIUM findings from the adversarial review."""

    def test_capacity_check_is_atomic(self, db, joined_guest):
        """Capacity is a hard ceiling enforced inside the write transaction."""
        gate = make_gate(db, FakeInjector(ok=True), capacity=1,
                         rate_burst=1000, rate_per_minute=1000)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        gate.submit(gid, sid, "first")
        with pytest.raises(SuggestionError) as ei:
            gate.submit(gid, sid, "second")
        assert ei.value.status_code == 503
        assert ei.value.receipt_state == ReceiptState.OVER_CAPACITY.value

    def test_reject_not_overwritten_by_inflight_injection(self, db, joined_guest):
        """A reject that lands while injection is in flight must not be flipped back."""
        started = threading.Event()

        def slow_inject(content, role="user", mode="queue"):
            started.set()
            time.sleep(0.5)
            return True

        gate = make_gate(db, slow_inject)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "suggest")

        approve_result = {}

        def do_approve():
            try:
                approve_result.update(gate.approve(
                    res["suggestion_id"], actor_role="host", session_id=sid))
            except SuggestionError as exc:
                approve_result["error"] = exc

        t = threading.Thread(target=do_approve)
        t.start()
        started.wait(timeout=2)  # inject_fn now in flight

        # Reject lands while injection is in flight.
        gate.reject(res["suggestion_id"], actor_role="host", session_id=sid)

        t.join(timeout=3)

        # The approve's txn2 status guard must not resurrect the rejected row.
        row = db.conn.execute(
            "SELECT status FROM suggestions WHERE id=?", (res["suggestion_id"],)
        ).fetchone()
        assert row["status"] == "rejected"
        # approve() either raised (409) or returned injected=False — never a clean injected=True.
        assert approve_result.get("injected") is not True

    def test_reject_expired_409(self, db, joined_guest, injector):
        gate = make_gate(db, injector, pending_ttl_seconds=60)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "stale")
        past = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
        with db.write_txn() as cur:
            cur.execute("UPDATE suggestions SET expires_at=? WHERE id=?", (past, res["suggestion_id"]))
        with pytest.raises(SuggestionError) as ei:
            gate.reject(res["suggestion_id"], actor_role="host", session_id=sid)
        assert ei.value.status_code == 409

    def test_cross_session_approve_404(self, db, joined_guest, injector):
        """approve is session-scoped: a suggestion_id from another session is 404."""
        gate = make_gate(db, injector)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "suggest")
        with pytest.raises(SuggestionError) as ei:
            gate.approve(res["suggestion_id"], actor_role="host", session_id="OTHER-SESSION")
        assert ei.value.status_code == 404

    def test_concurrent_approve_no_double_inject(self, db, joined_guest):
        """In-flight guard: a second approve during injection → 409."""
        import threading
        slow = FakeInjector(ok=True)
        started = threading.Event()

        def slow_inject(content, role="user", mode="queue"):
            started.set()
            time.sleep(0.5)
            return True

        gate = make_gate(db, slow_inject)
        gid, sid = joined_guest["guest_id"], joined_guest["session_id"]
        res = gate.submit(gid, sid, "suggest")

        first_result = {}

        def do_approve():
            first_result.update(gate.approve(res["suggestion_id"], actor_role="host", session_id=sid))

        t = threading.Thread(target=do_approve)
        t.start()
        started.wait(timeout=2)
        with pytest.raises(SuggestionError) as ei:
            gate.approve(res["suggestion_id"], actor_role="host", session_id=sid)
        assert ei.value.status_code == 409
        t.join(timeout=3)
        assert first_result["injected"] is True
