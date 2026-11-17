"""Unit tests for the COtrip corridor script. No network."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "colorado-traffic" / "scripts" / "cotrip_corridor.py"


def load_script():
    spec = importlib.util.spec_from_file_location("cotrip_corridor", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = load_script()


def feature(link, bearing, points=(260.0, 262.0), event_id="1", windows=None, begin=None):
    location = {
        "linkDirection": link,
        "routePositiveBearing": bearing,
        "primaryPoint": {"linearReference": points[0]},
    }
    if len(points) > 1:
        location["secondaryPoint"] = {"linearReference": points[1]}
    report = {"location": location}
    if windows is not None:
        report["scheduleOccurrences"] = windows
    if begin is not None:
        report["beginTime"] = {"time": begin}
    return {"properties": {"id": event_id, "eventReport": report, "active": True}}


class DirectionTests(unittest.TestCase):
    def test_i70_positive_is_eastbound(self):
        self.assertEqual(mod.direction(feature("POSITIVE_DIRECTION", "E")), "eastbound")

    def test_i70_negative_is_westbound(self):
        self.assertEqual(mod.direction(feature("NEGATIVE_DIRECTION", "E")), "westbound")

    def test_i25_positive_is_northbound(self):
        self.assertEqual(mod.direction(feature("POSITIVE_DIRECTION", "N")), "northbound")

    def test_i25_negative_is_southbound(self):
        self.assertEqual(mod.direction(feature("NEGATIVE_DIRECTION", "N")), "southbound")

    def test_both_directions_is_not_the_positive_bearing(self):
        self.assertEqual(mod.direction(feature("BOTH_DIRECTIONS", "E")), "both")

    def test_missing_bearing_is_unknown(self):
        self.assertEqual(mod.direction(feature("POSITIVE_DIRECTION", None)), "unknown")


class TimingTests(unittest.TestCase):
    def test_future_window_is_upcoming_even_if_active(self):
        item = feature(
            "POSITIVE_DIRECTION",
            "E",
            windows=[{"startTime": {"time": 2_000}, "endTime": {"time": 3_000}}],
        )
        self.assertEqual(mod.timing(item, 1_000), "upcoming")

    def test_open_window_is_now(self):
        item = feature(
            "POSITIVE_DIRECTION",
            "E",
            windows=[{"startTime": {"time": 500}, "endTime": {"time": 2_000}}],
        )
        self.assertEqual(mod.timing(item, 1_000), "now")

    def test_closed_window_is_ended(self):
        item = feature(
            "POSITIVE_DIRECTION",
            "E",
            windows=[{"startTime": {"time": 100}, "endTime": {"time": 200}}],
        )
        self.assertEqual(mod.timing(item, 1_000), "ended")

    def test_no_window_and_future_begin_is_upcoming(self):
        item = feature("POSITIVE_DIRECTION", "E", begin=5_000)
        self.assertEqual(mod.timing(item, 1_000), "upcoming")


class FilterTests(unittest.TestCase):
    def test_overlap_includes_a_segment_that_crosses_the_edge(self):
        self.assertTrue(mod.overlaps([253.0, 262.0], 259.0, 279.0))

    def test_empty_milepoints_do_not_match(self):
        self.assertFalse(mod.overlaps([], 259.0, 279.0))

    def test_west_of_the_box_does_not_match(self):
        self.assertFalse(mod.overlaps([240.0, 250.0], 259.0, 279.0))

    def test_strip_html_drops_tags_and_keeps_breaks(self):
        self.assertEqual(mod.strip_html("Lane closed<br>at <b>Quebec</b>"), "Lane closed\nat Quebec")

    def test_waze_id_is_not_labeled_cdot(self):
        item = mod.summarize(feature("POSITIVE_DIRECTION", "E", event_id="Waze-9"), 1_000)
        self.assertEqual(item["source"], "Waze via COtrip")

    def test_healthy_payload_is_not_an_empty_road(self):
        with self.assertRaises(SystemExit):
            mod.require_features({"healthy": True}, "https://example.test/events")


if __name__ == "__main__":
    unittest.main()
