"""Unit tests with a fake transport. Run: python -m unittest discover -s tests"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("parcel_plugin", ROOT / "__init__.py",
                                               submodule_search_locations=[str(ROOT)])
plugin = importlib.util.module_from_spec(_spec)
sys.modules["parcel_plugin"] = plugin
_spec.loader.exec_module(plugin)
from parcel_plugin import client as C  # noqa: E402
from parcel_plugin import tools as T  # noqa: E402

KEY = "test-key-should-never-leak"
CARRIERS = {
    "ups": {"name": "UPS"},
    "usps": {"name": "USPS"},
    "allied": {"name": "Allied Express", "extra_required": 1},
    "amzlus": {"name": "Amazon US", "name_variations": ["Amazon Logistics"]},
}
DELIVERY = {
    "carrier_code": "ups",
    "description": "Running shoes",
    "status_code": 4,
    "tracking_number": "1Z999AA10123456784",
    "date_expected": "2026-10-03 20:00",
    "timestamp_expected": 1791061200,  # 2026-10-03 20:00 UTC
    "events": [{"event": "Out for delivery", "date": "Oct 3, 7:02", "location": "Kansas City, MO"},
               {"event": "Arrived at facility", "date": "Oct 2, 22:10"}],
    "some_future_field": {"ignored": True},
}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeTransport:
    """Records requests; answers with queued (status, body) pairs or the carrier list."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        if request.full_url == C.CARRIERS_URL:
            return FakeResponse(json.dumps(CARRIERS).encode())
        status, body = self.responses.pop(0)
        raw = json.dumps(body).encode()
        if status != 200:
            raise urllib.error.HTTPError(request.full_url, status, "err", {}, io.BytesIO(raw))
        return FakeResponse(raw)

    def api_calls(self):
        return [r for r in self.requests if r.full_url != C.CARRIERS_URL]


class Clock:
    def __init__(self):
        self.now = 1_791_000_000.0

    def __call__(self):
        return self.now


class ParcelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, *responses):
        transport = FakeTransport(*responses)
        client = C.ParcelClient(KEY, data_dir=Path(self.tmp.name), transport=transport, clock=self.clock)
        return client, transport

    def test_reads_are_cached_and_summarized(self):
        client, transport = self.make((200, {"success": True, "deliveries": [DELIVERY]}))
        first = json.loads(T.handle_deliveries(client, {}))
        second = json.loads(T.handle_deliveries(client, {}))
        self.assertEqual(len(transport.api_calls()), 1)
        self.assertEqual(transport.api_calls()[0].get_header("Api-key"), KEY)
        self.assertIn("filter_mode=active", transport.api_calls()[0].full_url)
        self.assertFalse(first["from_cache"])
        self.assertTrue(second["from_cache"])
        item = first["deliveries"][0]
        self.assertEqual(item["status"], "out_for_delivery")
        self.assertEqual(item["carrier"], "UPS")
        self.assertEqual(item["latest_event"]["location"], "Kansas City, MO")
        self.assertNotIn("events", item)
        self.assertNotIn("some_future_field", json.dumps(item))
        self.assertTrue(item["expected"]["utc"].startswith("2026-10-03"))

    def test_tracking_filter_ignores_spacing(self):
        client, _ = self.make((200, {"success": True, "deliveries": [DELIVERY]}))
        out = json.loads(T.handle_deliveries(client, {"tracking_number": "1z 999aa1-0123456784",
                                                      "include_events": True}))
        self.assertEqual(out["count"], 1)
        self.assertEqual(len(out["deliveries"][0]["events"]), 2)

    def test_local_budget_stops_the_21st_read_and_serves_stale_cache(self):
        responses = [(200, {"success": True, "deliveries": [DELIVERY]})] * 20
        client, transport = self.make(*responses)
        for _ in range(20):
            json.loads(T.handle_deliveries(client, {"refresh": True}))
        out = json.loads(T.handle_deliveries(client, {"refresh": True}))
        self.assertEqual(len(transport.api_calls()), 20)
        self.assertTrue(out["stale"])
        self.assertIn("limit", out["warning"])
        self.clock.now += 3601
        self.assertEqual(client.budget()["deliveries_requests_left_this_hour"], 20)

    def test_auth_failure_is_clear_and_never_leaks_the_key(self):
        client, _ = self.make((401, {"success": False, "error_message": "Account not found"}))
        out = T.handle_deliveries(client, {})
        self.assertEqual(json.loads(out)["code"], "auth")
        self.assertIn("Account not found", out)
        self.assertNotIn(KEY, out)

    def test_missing_key(self):
        client = C.ParcelClient(None, data_dir=Path(self.tmp.name), transport=FakeTransport(),
                                key_resolver=lambda: None)
        self.assertEqual(json.loads(T.handle_deliveries(client, {}))["code"], "missing_key")

    def test_redirect_is_refused(self):
        handler = C._NoRedirect()
        with self.assertRaises(C.ParcelError):
            handler.redirect_request(None, None, 302, "Found", {}, "https://evil.example/")

    def test_bad_add_input_is_rejected_before_any_request(self):
        client, transport = self.make()
        cases = [
            ({"tracking_number": "1Z1", "carrier_code": "nope", "description": "x"}, "unknown_carrier"),
            ({"tracking_number": "ABC123", "carrier_code": "allied", "description": "x"}, "extra_required"),
            ({"tracking_number": "ABC123", "carrier_code": "ups", "description": ""}, "invalid"),
            ({"tracking_number": "<script>", "carrier_code": "ups", "description": "x"}, "invalid"),
        ]
        for args, code in cases:
            self.assertEqual(json.loads(T.handle_add(client, args))["code"], code, args)
        self.assertEqual(transport.api_calls(), [])
        self.assertEqual(client.budget()["add_requests_left_today"], 20)

    def test_add_skips_numbers_already_tracked(self):
        client, transport = self.make((200, {"success": True, "deliveries": [DELIVERY]}))
        T.handle_deliveries(client, {})
        out = json.loads(T.handle_add(client, {"tracking_number": DELIVERY["tracking_number"],
                                               "carrier_code": "ups", "description": "dup"}))
        self.assertTrue(out["already_tracked"])
        self.assertEqual(len(transport.api_calls()), 1)

    def test_add_posts_once_and_clears_the_cache(self):
        client, transport = self.make(
            (200, {"success": True, "deliveries": []}),
            (200, {"success": True}),
            (200, {"success": True, "deliveries": [DELIVERY]}),
        )
        T.handle_deliveries(client, {})
        out = json.loads(T.handle_add(client, {"tracking_number": "9400100000000000000000",
                                               "carrier_code": "USPS", "description": "Books"}))
        self.assertTrue(out["added"])
        self.assertEqual(out["adds_left_today"], 19)
        post = transport.api_calls()[1]
        self.assertEqual(post.get_method(), "POST")
        self.assertEqual(json.loads(post.data), {"tracking_number": "9400100000000000000000",
                                                 "carrier_code": "usps", "description": "Books",
                                                 "send_push_confirmation": False})
        after = json.loads(T.handle_deliveries(client, {}))
        self.assertFalse(after["from_cache"])
        self.assertEqual(after["count"], 1)

    def test_rejected_add_reports_parcels_reason(self):
        client, _ = self.make((400, {"success": False, "error_message": "Invalid tracking number"}))
        out = json.loads(T.handle_add(client, {"tracking_number": "ABC123", "carrier_code": "ups",
                                               "description": "x"}))
        self.assertIn("Invalid tracking number", out["error"])
        self.assertEqual(client.budget()["add_requests_left_today"], 19)

    def test_carrier_search(self):
        client, _ = self.make()
        out = json.loads(T.handle_carriers(client, {"query": "amazon logistics"}))
        self.assertEqual([m["carrier_code"] for m in out["matches"]], ["amzlus"])
        exact = json.loads(T.handle_carriers(client, {"query": "ups"}))
        self.assertEqual(exact["matches"][0]["carrier_code"], "ups")

    def test_slash_command_text(self):
        client, _ = self.make((200, {"success": True, "deliveries": [DELIVERY]}))
        text = T.format_for_command(T.handle_deliveries(client, {}))
        self.assertIn("Running shoes (UPS): out for delivery", text)


if __name__ == "__main__":
    unittest.main()
