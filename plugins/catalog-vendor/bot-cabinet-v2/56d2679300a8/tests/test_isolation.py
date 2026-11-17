"""The tests can't reach the user's real Duckwork, and a full install flow doesn't change it.

A past incident: a scratch DUCKWORK_HOME did not stop code from the real Duckwork install rewriting the real
launchers. So these tests don't trust the setting. They look at the real ~/.duckwork (read only) before and
after a complete add, set-up and remove, and fail if anything there moved. They also prove where Cabinet and
the Duckwork bridge point while the tests run.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _duckwork_fake import fake_delete, gateway_create, wipe_profiles
from _load import REAL_USER_HOME, SANDBOX, sub

duckwork = sub("duckwork_bridge")
installer = sub("installer")
paths = sub("paths")
sync = sub("sync")
catalog = sub("catalog")

REAL_HOME = REAL_USER_HOME
# Duckwork's default home: ~/.duckwork on macOS and Linux, %LOCALAPPDATA%\\duckwork on Windows.
REAL_DUCKWORK = Path(os.environ["LOCALAPPDATA"]) / "duckwork" if os.name == "nt" and os.environ.get("LOCALAPPDATA") else REAL_HOME / ".duckwork"


def real_state():
    """The parts of the real ~/.duckwork a stray write would change. Read only."""
    state = {}
    profiles = REAL_DUCKWORK / "profiles"
    state["profiles"] = sorted(p.name for p in profiles.iterdir()) if profiles.is_dir() else None
    for rel in ("config.yaml", "SOUL.md", "duckwork-agent/.duckwork/bin/duckwork", "duckwork-agent/.duckwork/bin/duckwork-acp"):
        p = REAL_DUCKWORK / rel
        state[rel] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    plugin_data = REAL_DUCKWORK / "state" / "bot-cabinet-v2"
    state["cabinet-data"] = sorted(x.name for x in plugin_data.iterdir()) if plugin_data.is_dir() else None
    return state


class Where(unittest.TestCase):
    def test_the_environment_is_the_sandbox(self):
        for var in ("DUCKWORK_HOME", "CABINET_DATA_DIR", "HOME"):
            self.assertTrue(Path(os.environ[var]).resolve().is_relative_to(SANDBOX.resolve()) if hasattr(Path, "is_relative_to")
                            else str(Path(os.environ[var]).resolve()).startswith(str(SANDBOX.resolve())), var)

    def test_cabinet_data_and_profiles_point_into_the_sandbox(self):
        self.assertTrue(str(paths.data_dir().resolve()).startswith(str(SANDBOX.resolve())))
        self.assertTrue(str(duckwork.profiles_root().resolve()).startswith(str(SANDBOX.resolve())))
        self.assertTrue(str(duckwork.profile_dir("anything").resolve()).startswith(str(SANDBOX.resolve())))

    def test_nothing_resolves_to_the_real_home(self):
        real = str(REAL_DUCKWORK.resolve())
        for p in (paths.data_dir(), duckwork.profiles_root(), paths.duckwork_home(), duckwork.profile_dir("scout")):
            self.assertFalse(str(p.resolve()).startswith(real), p)

    def test_the_data_folder_override_is_honoured_and_the_default_is_under_the_duckwork_home(self):
        with mock.patch.dict(os.environ, {"CABINET_DATA_DIR": ""}, clear=False):
            os.environ.pop("CABINET_DATA_DIR")
            self.assertEqual(paths.data_dir(create=False), paths.duckwork_home() / "state" / "bot-cabinet-v2")
        self.assertEqual(paths.data_dir(create=False), Path(os.environ["CABINET_DATA_DIR"]))

    def test_the_real_home_is_not_where_this_process_thinks_home_is(self):
        self.assertNotEqual(Path.home().resolve(), REAL_HOME.resolve())


class RunnerImports(unittest.TestCase):
    def test_the_runner_loads_without_pwd_as_on_windows(self):
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location("cabinet_runner_check", Path(__file__).resolve().parent / "run_with_duckwork.py")
        mod = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"pwd": None}):  # None makes "import pwd" fail, as it does on Windows
            spec.loader.exec_module(mod)
            self.assertTrue(str(mod.real_home()))


class RealDuckworkStaysPut(unittest.TestCase):
    def test_a_full_add_set_up_and_remove_changes_nothing_real(self):
        before = real_state()
        with tempfile.TemporaryDirectory() as data, mock.patch.dict(os.environ, {"CABINET_DATA_DIR": data}), \
                mock.patch.object(duckwork, "delete_profile", side_effect=fake_delete):
            wipe_profiles()
            catalog.set_active(None)
            plan = installer.plan_bot("scout")
            gateway_create(plan["create"]["params"])
            one = installer.confirm(plan["planId"])
            crew_plan = installer.plan_crew("personal-planning-desk")
            made = []
            for m in crew_plan["members"]:
                if m["mode"] == "create":
                    gateway_create(m["create"]["params"])
                    made.append(m["profile"])
            crew = installer.confirm_crew(crew_plan["planId"], made)
            installer.save_kit("Kit", {"botName": "Kit"}, "x")
            installer.remove("crew", crew["crew"]["id"], True)
            installer.remove("bot", one["install"]["id"], True)
            sync.refresh(Path(data), lambda url, timeout: (_ for _ in ()).throw(OSError("offline")))
            wipe_profiles()
        self.assertEqual(real_state(), before)

    def test_removal_only_ever_names_profiles_inside_the_sandbox(self):
        seen = []
        with tempfile.TemporaryDirectory() as data, mock.patch.dict(os.environ, {"CABINET_DATA_DIR": data}), \
                mock.patch.object(duckwork, "delete_profile", side_effect=lambda n: (seen.append(duckwork.profile_dir(n)), fake_delete(n))):
            wipe_profiles()
            plan = installer.plan_bot("scout")
            gateway_create(plan["create"]["params"])
            iid = installer.confirm(plan["planId"])["install"]["id"]
            installer.remove("bot", iid, True)
            wipe_profiles()
        self.assertEqual(len(seen), 1)
        self.assertTrue(str(seen[0].resolve()).startswith(str(SANDBOX.resolve())))

    def test_the_real_install_is_never_imported_from(self):
        try:
            import duckwork_cli
        except ImportError:
            return  # no Duckwork here: nothing to leak
        real_code = str((REAL_DUCKWORK / "duckwork-agent").resolve())
        self.assertFalse(str(Path(duckwork_cli.__file__).resolve()).startswith(real_code),
                         "tests must run against a separate clone of Duckwork (tests/run_with_duckwork.py)")


if __name__ == "__main__":
    unittest.main()
