import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hab_builder", ROOT / "builder.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def plan():
    return {"name": "Release Writer", "slug": "release-writer", "description": "Write useful release notes.",
            "instructions": "Use the supplied facts. Keep it under 150 words. Ask for missing details.",
            "starters": ["Write a release announcement."], "success_checks": ["Preserves the version number"],
            "toolsets": [], "skills": []}


class Llm:
    def complete_structured(self, **kwargs):
        if kwargs["purpose"].endswith("interview"):
            return SimpleNamespace(parsed={"intro": "Let's tailor it to your work.", "questions": [
                {"question": "Who reads these announcements?", "hint": "Name the audience", "options": ["Customers", "Developers"]}]})
        return SimpleNamespace(parsed=plan())

    def complete(self, **kwargs):
        self.messages = kwargs["messages"]
        return SimpleNamespace(text="Duckwork Agent Builder 1.0.0 turns a brief into a specialist.")


class BuilderTests(unittest.TestCase):
    def setUp(self):
        from duckwork_constants import set_duckwork_home_override
        self.temp = tempfile.TemporaryDirectory()
        self.token = set_duckwork_home_override(Path(self.temp.name) / "profile-a")
        self.llm = Llm()
        self.engine = builder.Builder(self.llm)

    def tearDown(self):
        from duckwork_constants import reset_duckwork_home_override
        reset_duckwork_home_override(self.token)
        self.temp.cleanup()

    def draft(self):
        return self.engine.build({"brief": "Write customer release announcements", "references": [
            {"name": "brief.md", "content": "Release: 1.0.0. Do not invent prices."}]})["draft"]

    def test_interview_answers_and_reference_grounding_survive_export(self):
        result = self.engine.interview({"brief": "Write announcements"})
        self.assertTrue(result["interview"]["questions"])
        draft = self.engine.build({"brief": "Write announcements", "answers": [
            {"question": "Audience?", "answer": "Customers"}], "references": [
            {"name": "../data.md", "content": "Release: 1.0.0"}]})["draft"]
        self.assertIn("Customers", draft["brief"])
        exported = self.engine.export({"id": draft["id"]})["blueprint"]
        self.assertEqual(exported["references"][0]["name"], "../data.md")
        self.assertEqual(set(exported), {"format", "format_version", "plan", "references"})
        self.assertIn("reference data", builder.make_soul(draft))

    def test_profile_storage_isolation_a_b_a(self):
        from duckwork_constants import set_duckwork_home_override, reset_duckwork_home_override
        a = self.draft()
        token = set_duckwork_home_override(Path(self.temp.name) / "profile-b")
        try:
            self.assertEqual(self.engine.list({})["drafts"], [])
            with self.assertRaises(ValueError):
                self.engine.get({"id": a["id"]})
            b = self.draft()
            self.assertNotEqual(a["id"], b["id"])
        finally:
            reset_duckwork_home_override(token)
        self.assertEqual(self.engine.get({"id": a["id"]})["draft"]["id"], a["id"])
        self.assertEqual(len(self.engine.list({})["drafts"]), 1)

    def test_exact_capability_pin_survives_native_runtime_resolution(self):
        from duckwork_constants import set_duckwork_home_override, reset_duckwork_home_override
        from duckwork_cli.config import load_config
        from duckwork_cli.tools_config import _get_platform_tools
        for selected in ([], ["web"]):
            with self.subTest(selected=selected):
                blueprint = plan()
                blueprint["toolsets"] = selected
                self.llm.complete_structured = lambda **kw: SimpleNamespace(parsed=blueprint)
                draft = self.engine.build({"brief":"Write supplied release facts", "capabilities":{
                    "toolsets":["web","file"], "skills":["duckwork-agent"]}})["draft"]
                self.engine.created({"id":draft["id"],"version":1,"profile":"release-writer"})
                bot_home = Path(self.temp.name)/("bot-web" if selected else "bot-empty")
                bot_home.mkdir()
                (bot_home/"config.yaml").write_text("platform_toolsets:\n  cli: [duckwork-cli]\n")
                with patch("duckwork_cli.profiles.get_profile_dir", return_value=bot_home):
                    self.engine.pin_capabilities({"id":draft["id"],"version":1})
                token = set_duckwork_home_override(bot_home)
                try:
                    cfg = load_config()
                    self.assertEqual(cfg["platform_toolsets"]["cli"], selected)
                    self.assertEqual(_get_platform_tools(cfg,"cli",include_default_mcp_servers=False),set(selected))
                    self.assertIsInstance(cfg["known_builtin_toolsets"],dict)
                finally:
                    reset_duckwork_home_override(token)
                self.assertEqual(self.engine.get({"id":draft["id"]})["draft"]["profile"],"release-writer")

    def test_invalid_optional_suggestions_keep_questions_answerable(self):
        for options, expected in ((None, []), ("unexpected text", []),
                                  ([" Web apps ", "Web apps", None, {}, "", "x" * 151,
                                    "Scripts", "Mobile", "Desktop", "Other"],
                                   ["Web apps", "Scripts", "Mobile", "Desktop"])):
            with self.subTest(options=options):
                self.llm.complete_structured = lambda **kw: SimpleNamespace(parsed={
                    "intro": "Let's tailor your coding specialist.", "questions": [
                        {"question": "What will you build?", "hint": None, "options": options}]})
                result = self.engine.interview({"brief": "hello i need it to code"})["interview"]
                self.assertEqual(result["questions"][0]["question"], "What will you build?")
                self.assertEqual(result["questions"][0]["options"], expected)
                self.assertEqual(result["questions"][0]["hint"], "")

    def test_model_timeout_never_records_a_fake_draft(self):
        def fail(**kwargs):
            self.assertGreater(kwargs["timeout"], 0)
            raise TimeoutError("Model timed out")
        self.llm.complete_structured = fail
        with self.assertRaises(TimeoutError):
            self.engine.build({"brief": "Write announcements"})
        self.assertEqual(self.engine.list({})["drafts"], [])

    def test_trial_uses_real_blueprint_references_and_prior_turns(self):
        draft = self.draft()
        one = self.engine.trial({"id": draft["id"], "message": "Write it"})
        self.engine.trial({"id": draft["id"], "message": "Make it shorter"})
        self.assertEqual([m["role"] for m in self.llm.messages], ["system", "user", "assistant", "user"])
        self.assertIn("Release: 1.0.0", self.llm.messages[0]["content"])
        self.assertEqual(one["trial"]["version"], draft["version"])
        refined = self.engine.refine({"id": draft["id"], "brief": "Use bullets"})["draft"]
        self.engine.trial({"id": draft["id"], "message": "Try again"})
        self.assertEqual(len(self.llm.messages), 2)
        self.assertGreater(refined["version"], draft["version"])

    def test_stale_inflight_model_reply_cannot_overwrite_an_edit(self):
        draft = self.draft()
        def during_call(**kwargs):
            changed = plan(); changed["instructions"] = "Preserve the new instruction."
            self.engine.edit({"id": draft["id"], "plan": changed})
            return SimpleNamespace(text="A late response")
        self.llm.complete = during_call
        with self.assertRaisesRegex(ValueError, "another window"):
            self.engine.trial({"id": draft["id"], "message": "Write it"})
        latest = self.engine.get({"id": draft["id"]})["draft"]
        self.assertEqual(latest["plan"]["instructions"], "Preserve the new instruction.")
        self.assertEqual(latest["trials"], [])

    def test_comparison_uses_same_task_with_original_and_refined_instructions(self):
        draft = self.draft()
        changed = plan(); changed["instructions"] = "Write exactly three useful bullets."
        revised = self.engine.edit({"id": draft["id"], "plan": changed})["draft"]
        calls = []
        def capture(**kwargs):
            calls.append(kwargs["messages"])
            return SimpleNamespace(text=f"Result {len(calls)}")
        self.llm.complete = capture
        comparison = self.engine.compare({"id": draft["id"], "version": revised["version"], "message": "Write the announcement"})["comparison"]
        self.assertEqual(calls[0][1], calls[1][1])
        self.assertIn("under 150 words", calls[0][0]["content"])
        self.assertIn("exactly three", calls[1][0]["content"])
        self.assertEqual([o["version"] for o in comparison["outputs"]], [1, 2])
        copied = self.engine.duplicate({"id": draft["id"]})["draft"]
        self.assertNotEqual(copied["id"], draft["id"])
        self.assertEqual(copied["plan"]["instructions"], changed["instructions"])
        self.assertIsNone(copied["profile"])

    def test_hallucinated_capability_and_unsafe_profile_names_are_rejected(self):
        bad = plan(); bad["toolsets"] = ["imaginary"]
        with self.assertRaisesRegex(ValueError, "Unavailable"):
            builder.validate_plan(bad, {"toolsets": [], "skills": []})
        for slug in ("../default", "default", "C:\\escape", "release writer"):
            bad = plan(); bad["slug"] = slug
            with self.assertRaises(ValueError):
                builder.validate_plan(bad, {"toolsets": [], "skills": []})

    def test_publish_lifecycle_preserves_trial_version_and_prevents_draft_deletion(self):
        draft = self.draft()
        self.engine.trial({"id": draft["id"], "message": "Write it"})
        spec = self.engine.publish_spec({"id": draft["id"], "version": draft["version"]})
        self.assertIn("Release Writer", spec["soul"])
        saved = self.engine.created({"id": draft["id"], "version": draft["version"], "profile": "release-writer"})["draft"]
        published = self.engine.published({"id": draft["id"]})["draft"]
        self.assertTrue(published["published"])
        self.assertEqual(saved["version"], published["trials"][0]["version"])
        with self.assertRaises(ValueError):
            self.engine.delete({"id": draft["id"]})

    def test_failures_are_not_recorded_as_successful_model_output(self):
        draft = self.draft()
        self.llm.complete = lambda **kwargs: SimpleNamespace(text="")
        with self.assertRaises(ValueError):
            self.engine.trial({"id": draft["id"], "message": "Write it"})
        self.assertEqual(self.engine.get({"id": draft["id"]})["draft"]["trials"], [])
        with self.assertRaises(ValueError):
            builder.clean_references([{"name": "big.md", "content": "x" * 60001}])

    def test_portable_installer_is_transactional_and_leaves_data_alone(self):
        spec = importlib.util.spec_from_file_location("hab_install", ROOT / "install.py")
        installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
        destination = Path(self.temp.name) / "Native Duckwork home with spaces"
        data = destination / "plugin-data" / builder.PLUGIN_ID / "keep.txt"
        data.parent.mkdir(parents=True); data.write_text("saved draft")
        installed = installer.install(ROOT, destination)
        self.assertTrue((installed / "desktop" / "plugin.js").is_file())
        with self.assertRaises(FileExistsError):
            installer.install(ROOT, destination)
        installer.install(ROOT, destination, update=True)
        self.assertEqual(data.read_text(), "saved draft")
        self.assertFalse((installed / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
