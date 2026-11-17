"""Office metadata must stay inside its owning synthetic profile database."""
import contextlib
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import time
import types
import unittest
from unittest.mock import patch


API = Path(__file__).resolve().parents[1] / "dashboard/plugin_api.py"


class DashboardAuthorityTest(unittest.TestCase):
    def test_secondary_profile_current_session_and_missing_authority(self):
        with tempfile.TemporaryDirectory(prefix="office-authority-") as tmp:
            root = Path(tmp)
            other = root / "profiles" / "other"
            other.mkdir(parents=True)
            (other / "profile.yaml").write_text(
                "display_name: Worker\n", encoding="utf-8"
            )
            now = time.time()
            for home, session_id, title, model in (
                (root, "root-only", "Root private work", "root-model"),
                (other, "other-only", "Worker task", "worker-model"),
            ):
                with contextlib.closing(sqlite3.connect(home / "state.db")) as db:
                    db.execute(
                        "CREATE TABLE sessions (id TEXT, title TEXT, model TEXT, "
                        "started_at REAL, last_activity_at REAL, ended_at REAL, "
                        "hidden INTEGER, archived INTEGER, input_tokens INTEGER, "
                        "output_tokens INTEGER, actual_cost_usd REAL, "
                        "estimated_cost_usd REAL)"
                    )
                    db.execute(
                        "INSERT INTO sessions VALUES "
                        "(?, ?, ?, ?, ?, NULL, 0, 0, 10, 5, 0.1, NULL)",
                        (session_id, title, model, now - 30, now),
                    )
                    db.execute(
                        "INSERT INTO sessions VALUES "
                            "('hidden-only', 'Internal automation', 'secret-model', "
                        "?, ?, NULL, 1, 0, 0, 0, 0, NULL)",
                        (now - 10, now),
                    )
                    if home == other:
                        db.execute(
                            "INSERT INTO sessions VALUES "
                            "('ended', 'Finished', 'retired-model', "
                            "?, ?, ?, 0, 0, 0, 0, 0, NULL)",
                            (now - 40, now - 2, now - 2),
                        )
                    db.commit()

            spec = importlib.util.spec_from_file_location("office_authority", API)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            try:
                with patch.object(module, "DUCKWORK_HOME", str(root)), patch.object(
                    module, "resolve_gateway_liveness",
                    return_value=types.SimpleNamespace(running=False, source=None),
                ):
                    entries = {
                        item["profile"]: item for item in module._collect_state()
                    }
                    self.assertEqual(
                        entries["default"]["latest_session_id"], "root-only"
                    )
                    self.assertEqual(
                        entries["other"]["latest_session_id"], "other-only"
                    )
                    # Recorded recency alone is not running-turn authority.
                    self.assertIsNone(entries["other"]["current_task"])
                    self.assertIsNone(entries["other"]["current_model"])
                    self.assertEqual(entries["other"]["recent_task"], "Worker task")
                    self.assertEqual(entries["other"]["recent_model"], "worker-model")
                    self.assertEqual(entries["other"]["tokens_total"], 15)
                    self.assertTrue(entries["other"]["session_stats_available"])
                    self.assertEqual(entries["other"]["active_sessions"], 2)
                    self.assertNotIn("Root private work", str(entries["other"]))
                    self.assertNotIn("secret-model", str(entries["other"]))

                    with contextlib.closing(sqlite3.connect(other / "state.db")) as db:
                        db.execute(
                            "UPDATE sessions SET last_activity_at = ? "
                            "WHERE id = 'other-only'",
                            (now - 200,),
                        )
                        db.commit()
                    module._close_all_ro_conns()
                    stale = module._read_profile("other")
                    self.assertIsNone(stale["current_task"])
                    self.assertIsNone(stale["current_model"])
                    self.assertEqual(stale["latest_session_id"], "ended")
                    # The latest RECORDED session is reported as recent; a stale
                    # session is still never presented as current.
                    self.assertEqual(stale["recent_task"], "Finished")
                    self.assertEqual(stale["recent_model"], "retired-model")

                    with contextlib.closing(sqlite3.connect(other / "state.db")) as db:
                        db.execute("DROP TABLE sessions")
                        db.commit()
                    module._close_all_ro_conns()
                    self.assertFalse(
                        module._read_session_stats("other")["session_stats_available"]
                    )
                    self.assertEqual(
                        module._read_session_metadata("other"),
                        {
                            "latest_session_id": None,
                            "current_task": None,
                            "current_model": None,
                            "recent_task": None,
                            "recent_model": None,
                        },
                    )
                    with self.assertRaises(ValueError):
                        module._read_session_metadata("../default")
            finally:
                module._close_all_ro_conns()

    def test_missing_and_empty_profile_database_have_distinct_usage_authority(self):
        with tempfile.TemporaryDirectory(prefix="office-stats-") as tmp:
            spec = importlib.util.spec_from_file_location("office_stats", API)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            try:
                with patch.object(module, "DUCKWORK_HOME", tmp):
                    missing = module._read_session_stats("default")
                    self.assertEqual(missing["tokens_total"], 0)
                    self.assertFalse(missing["session_stats_available"])
                    db_path = Path(tmp) / "state.db"
                    with contextlib.closing(sqlite3.connect(db_path)) as db:
                        db.execute(
                            "CREATE TABLE sessions (ended_at REAL, "
                            "last_activity_at REAL, "
                            "input_tokens INTEGER, output_tokens INTEGER, "
                            "actual_cost_usd REAL, estimated_cost_usd REAL)"
                        )
                        db.commit()
                    empty = module._read_session_stats("default")
                    self.assertEqual(empty["tokens_total"], 0)
                    self.assertTrue(empty["session_stats_available"])
            finally:
                module._close_all_ro_conns()
