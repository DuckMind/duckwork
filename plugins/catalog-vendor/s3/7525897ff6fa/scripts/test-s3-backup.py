#!/usr/bin/env python3
"""Hermetic FakeS3 and FakeCtx tests for the standalone plugin."""
from __future__ import annotations

import argparse
import importlib
import io
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from s3_backup import rules, storage  # noqa: E402


class FakeS3:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.deletes: list[str] = []
        self.gets = 0

    def put_object(self, *, Bucket, Key, Body, IfNoneMatch=None):
        if IfNoneMatch == "*" and Key in self.objects:
            raise RuntimeError("precondition failed")
        self.objects[Key] = Body.read() if hasattr(Body, "read") else bytes(Body)

    def get_object(self, *, Bucket, Key):
        self.gets += 1
        return {"Body": io.BytesIO(self.objects[Key])}

    def list_objects_v2(self, *, Bucket, Prefix, ContinuationToken=None):
        keys = sorted(key for key in self.objects if key.startswith(Prefix))
        start = int(ContinuationToken or 0)
        page = keys[start : start + 2]
        end = start + len(page)
        result = {"Contents": [{"Key": k, "Size": len(self.objects[k])} for k in page], "IsTruncated": end < len(keys)}
        if end < len(keys):
            result["NextContinuationToken"] = str(end)
        return result

    def delete_object(self, *, Bucket, Key):
        self.deletes.append(Key)
        self.objects.pop(Key, None)


class FakeCtx:
    def __init__(self):
        self.tools, self.cli, self.skills = [], [], []

    def register_tool(self, **kwargs): self.tools.append(kwargs)
    def register_cli_command(self, *args, **kwargs): self.cli.append((args, kwargs))
    def register_skill(self, *args): self.skills.append(args)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def storage_tests(fake):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        file = root / "one.txt"
        file.write_bytes(b"one")
        ok, report = storage.push(str(file), "one.txt", "bucket", False)
        require(ok and report["files"] == 1 and report["bytes"] == 3, "file push")
        tree = root / "tree"
        (tree / "nested").mkdir(parents=True)
        (tree / "a").write_bytes(b"alpha")
        (tree / "nested" / "b").write_bytes(b"beta")
        ok, report = storage.push(str(tree), "backup", "bucket", False)
        require(ok and report["files"] == 2 and report["bytes"] == 9, "directory push")
        require(set(fake.objects) == {"one.txt", "backup/a", "backup/nested/b"}, "POSIX keys")
        file.write_bytes(b"changed")
        ok, report = storage.push(str(file), "one.txt", "bucket", False)
        require(ok and report["skipped"] == 1 and fake.objects["one.txt"] == b"one", "skip overwrite")
        ok, report = storage.push(str(file), "one.txt", "bucket", True)
        require(ok and report["files"] == 1 and fake.objects["one.txt"] == b"changed", "force overwrite")

        destination = root / "restore"
        ok, report = storage.pull("backup", str(destination), "bucket")
        require(ok and report == {"files": 2, "bytes": 9}, "round-trip report")
        require((destination / "nested" / "b").read_bytes() == b"beta", "round-trip content")
        gets = fake.gets
        ok, listing = storage.ls("backup", "bucket")
        require(ok and listing["keys"] == ["backup/a", "backup/nested/b"] and fake.gets == gets, "list metadata")

        fake.objects["evil/../escape"] = b"bad"
        fake.objects["evil/link/pwn"] = b"bad"
        outside = root / "outside"
        outside.mkdir()
        (destination / "link").symlink_to(outside, target_is_directory=True)
        ok, payload = storage.pull("evil", str(destination), "bucket")
        require(not ok and "unsafe" in payload["error"]["message"].lower(), "traversal guard")
        require(not (outside / "pwn").exists() and not (root / "escape").exists(), "escape prevention")

        before = len(fake.deletes)
        ok, _ = storage.rm("one.txt", "bucket", False)
        require(not ok and len(fake.deletes) == before, "confirmation required")
        ok, report = storage.rm("one.txt", "bucket", True)
        require(ok and report["deleted"] == 1, "exact deletion")
        fake.objects.update({"old/a": b"a", "old/b": b"bb"})
        ok, _ = storage.rm("old", "bucket", True, False)
        require(not ok, "recursive deletion guard")
        ok, report = storage.rm("old", "bucket", True, True)
        require(ok and report["deleted"] == 2, "recursive deletion")


def rules_test():
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as stream:
        stream.write("run-output:\n  prefix: backups/{date}/{year}/{month}/{day}/{ts}\n  source: ~/reports\n")
        path = stream.name
    try:
        fixed = datetime(2024, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
        value = rules.resolve("run-output", "push", path, fixed)
        require(value["local"] == os.path.expanduser("~/reports"), "rule source")
        require(value["remote"] == "backups/2024-02-03/2024/02/03/2024-02-03T04:05:06+00:00", "rule templates")
        require(rules.resolve("run-output", "pull", path, fixed) == value, "rule operation")
        try: rules.resolve("missing", "push", path, fixed)
        except KeyError: pass
        else: raise AssertionError("missing rule accepted")
    finally:
        Path(path).unlink()


def registration_test():
    sys.modules.pop("__init__", None)
    plugin = importlib.import_module("__init__")
    ctx = FakeCtx()
    plugin.register(ctx)
    names = [entry["name"] for entry in ctx.tools]
    require(names == ["s3-push", "s3-pull", "s3-ls", "s3-rm"], "tool registration")
    require(all(entry["override"] is False for entry in ctx.tools), "override policy")
    require(len(ctx.cli) == 1 and ctx.cli[0][1]["name"] == "s3", "CLI registration")
    require(len(ctx.skills) == 1 and ctx.skills[0][0] == "s3", "skill registration")
    parser = argparse.ArgumentParser()
    plugin.register_cli(parser)
    help_text = parser.format_help()
    require(all(word in help_text for word in ("push", "pull", "ls", "rm")), "CLI help")
    args = parser.parse_args(["push", "/tmp/backups", "duckwork-backups/test/", "--force"])
    require(
        args.positionals == ["/tmp/backups", "duckwork-backups/test/"] and args.force,
        "CLI positional push",
    )


def main():
    os.environ.update({"S3_BACKUP_BUCKET": "bucket", "S3_BACKUP_ENDPOINT": "https://invalid", "S3_BACKUP_REGION": "us-east-1", "S3_BACKUP_ACCESS_KEY": "test", "S3_BACKUP_SECRET_KEY": "test"})
    fake = FakeS3()
    original = storage._make_client
    storage._make_client = lambda cfg: fake
    tests = [("storage operations", lambda: storage_tests(fake)), ("rules", rules_test), ("registration", registration_test)]
    failed = 0
    try:
        for name, test in tests:
            try:
                test()
                print(f"PASS {name}")
            except Exception as exc:
                failed += 1
                print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    finally:
        storage._make_client = original
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
