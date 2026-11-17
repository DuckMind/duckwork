"""JSON CLI. Exit 0 means completed analysis, not that all findings passed."""
import argparse
import json
from pathlib import Path

from .contrast import check_contrast
from .direction import make_direction
from .inspection import inspect_project
from .library import get_reference


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def _json_file(filename):
    path = Path(filename)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("JSON input must not exceed 2 MiB")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    """Print one JSON object; return an explicit status for every operational path."""
    parser = _Parser(prog="hardlight", description="Stateless frontend design and navigation aids")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("styles", help="List shipped style IDs")
    ref = sub.add_parser("reference", help="Read an allowlisted reference")
    ref.add_argument("topic", nargs="?", default="index")
    ref.add_argument("--style")
    direction = sub.add_parser("direction", help="Plan directions from a JSON object")
    direction.add_argument("--input", required=True, metavar="FILE.json")
    inspect = sub.add_parser("inspect", help="Bounded read-only frontend scan")
    inspect.add_argument("root")
    inspect.add_argument("--max-files", type=int, default=120)
    contrast = sub.add_parser("contrast", help="Measure opaque sRGB color pairs")
    contrast.add_argument("--pairs", required=True, metavar="FILE.json")
    navigation = sub.add_parser("navigation", help="Analyze an explicit route graph")
    navigation.add_argument("--input", required=True, metavar="FILE.json")
    browser = sub.add_parser("browser", help="Optional installed-browser audit")
    browser.add_argument("target")
    browser.add_argument("--output-dir", required=True)
    browser.add_argument("--executable")
    try:
        args = parser.parse_args(argv)
        if args.command == "styles":
            result = get_reference()
        elif args.command == "reference":
            result = get_reference(args.topic, args.style)
        elif args.command == "direction":
            payload = _json_file(args.input)
            if not isinstance(payload, dict):
                raise ValueError("direction input must be a JSON object with brief and optional surface, authority, styles, context")
            result = make_direction(**payload)
        elif args.command == "inspect":
            result = inspect_project(args.root, args.max_files)
        elif args.command == "contrast":
            result = check_contrast(_json_file(args.pairs))
        elif args.command == "navigation":
            from .navigation import analyze_navigation
            payload = _json_file(args.input)
            if not isinstance(payload, dict):
                raise ValueError("navigation input must be a JSON object with pages, tasks and optional home")
            result = analyze_navigation(**payload)
        else:
            from .browser import audit_page
            result = audit_page(args.target, args.output_dir, executable=args.executable)
    except (OSError, ValueError, TypeError, ImportError) as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0 if result.get("ok") is True else 1
