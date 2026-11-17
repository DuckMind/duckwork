"""CLI subtree: `duckwork s3 push|pull|ls|rm`."""

from __future__ import annotations

import argparse
import json
import sys

try:
    from . import rules as rules_mod
    from . import storage
    from .config import load_config
except ImportError:  # top-level import when run as a script (tests)
    import rules as rules_mod
    import storage
    from config import load_config


def _resolve(args: argparse.Namespace, op: str):
    cfg = load_config()
    if args.rule:
        rules = rules_mod.load_rules(cfg.rules_path)
        r = rules_mod.resolve(rules, args.rule, op)
        local = r.get("local") or args.local
        remote = r.get("remote") or args.remote
    else:
        local = args.local
        remote = args.remote

    positionals = getattr(args, "positionals", ())
    if op == "push":
        local = local or (positionals[0] if len(positionals) > 0 else None)
        remote = remote or (positionals[1] if len(positionals) > 1 else None)
    elif op == "pull":
        remote = remote or (positionals[0] if len(positionals) > 0 else None)
        local = local or (positionals[1] if len(positionals) > 1 else None)
    else:
        remote = remote or (positionals[0] if positionals else None)
    return local, remote


def _cmd_push(args: argparse.Namespace) -> int:
    local, remote = _resolve(args, "push")
    if not local:
        print(json.dumps({"ok": False, "error": "push requires --local or a rule"}))
        return 2
    if not remote:
        print(json.dumps({"ok": False, "error": "push requires --remote or a rule"}))
        return 2
    bucket = load_config().bucket
    if not bucket:
        print(json.dumps({"ok": False, "error": "S3_BACKUP_BUCKET not configured"}))
        return 2
    ok, payload = storage.push(local, remote, bucket, bool(args.force))
    print(json.dumps({"ok": ok, **payload}, ensure_ascii=False))
    return 0 if ok else 1


def _cmd_pull(args: argparse.Namespace) -> int:
    local, remote = _resolve(args, "pull")
    if not local:
        print(json.dumps({"ok": False, "error": "pull requires --local or a rule"}))
        return 2
    if not remote:
        print(json.dumps({"ok": False, "error": "pull requires --remote or a rule"}))
        return 2
    bucket = load_config().bucket
    if not bucket:
        print(json.dumps({"ok": False, "error": "S3_BACKUP_BUCKET not configured"}))
        return 2
    ok, payload = storage.pull(local, remote, bucket)
    print(json.dumps({"ok": ok, **payload}, ensure_ascii=False))
    return 0 if ok else 1


def _cmd_ls(args: argparse.Namespace) -> int:
    _local, remote = _resolve(args, "ls")
    if not remote:
        print(json.dumps({"ok": False, "error": "ls requires --remote or a rule"}))
        return 2
    bucket = load_config().bucket
    if not bucket:
        print(json.dumps({"ok": False, "error": "S3_BACKUP_BUCKET not configured"}))
        return 2
    ok, payload = storage.ls(remote, bucket)
    print(json.dumps({"ok": ok, **payload}, ensure_ascii=False))
    return 0 if ok else 1


def _cmd_rm(args: argparse.Namespace) -> int:
    _local, remote = _resolve(args, "rm")
    if not remote:
        print(json.dumps({"ok": False, "error": "rm requires --remote or a rule"}))
        return 2
    bucket = load_config().bucket
    if not bucket:
        print(json.dumps({"ok": False, "error": "S3_BACKUP_BUCKET not configured"}))
        return 2
    ok, payload = storage.rm(remote, bucket, bool(args.confirm))
    print(json.dumps({"ok": ok, **payload}, ensure_ascii=False))
    return 0 if ok else 1


def register(subparser: argparse.ArgumentParser) -> None:
    """Build the `duckwork s3` subcommand tree."""
    subs = subparser.add_subparsers(dest="s3_action", required=True)

    def _add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--rule", help="Named rule from the rules YAML")
        p.add_argument("--local", "--dst", dest="local", help="Local file/dir (push source / pull target)")
        p.add_argument("--remote", "--src", dest="remote", help="Remote key/prefix")

    p = subs.add_parser("push", help="Upload file or dir to the bucket")
    _add_common(p)
    p.add_argument("positionals", nargs="*", metavar="PATH", help="Local source followed by remote key/prefix")
    p.add_argument("--force", action="store_true", help="Overwrite existing keys")
    p.set_defaults(func=_cmd_push)

    p = subs.add_parser("pull", help="Download key/prefix to a local dir")
    _add_common(p)
    p.add_argument("positionals", nargs="*", metavar="PATH", help="Remote key/prefix followed by local destination")
    p.set_defaults(func=_cmd_pull)

    p = subs.add_parser("ls", help="List objects under a prefix")
    _add_common(p)
    p.add_argument("positionals", nargs="*", metavar="PREFIX", help="Remote key/prefix")
    p.set_defaults(func=_cmd_ls)

    p = subs.add_parser("rm", help="Delete an object (requires --confirm)")
    _add_common(p)
    p.add_argument("positionals", nargs="*", metavar="KEY", help="Remote key/prefix")
    p.add_argument("--confirm", action="store_true", help="Required to delete")
    p.set_defaults(func=_cmd_rm)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="s3")
    register(parser)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
