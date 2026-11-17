"""Duckwork adapter for the Claude SEO project's portable analysis library."""

from __future__ import annotations

import argparse
import os
import subprocess
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
HTML_EXTENSIONS = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".php", ".ejs"}
SAFE_BASE_ENV = {
    "PATH", "HOME", "USER", "LOGNAME", "USERPROFILE", "SYSTEMROOT", "WINDIR",
    "COMSPEC", "PATHEXT", "TMP", "TEMP", "TMPDIR", "LANG", "LC_ALL",
    "LC_CTYPE", "TZ", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
}


def _auth_contract() -> Any:
    import importlib.util

    path = ROOT / "scripts" / "auth_contract.py"
    spec = importlib.util.spec_from_file_location("duckwork_seo_auth_contract", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("credential allowlist is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_runtime() -> Any:
    import importlib.util

    path = ROOT / "scripts" / "runtime.py"
    spec = importlib.util.spec_from_file_location("duckwork_seo_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("isolated runtime is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safe_child_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key in SAFE_BASE_ENV}


def _validate_jsonld(content: str, filepath: str) -> list[str]:
    import importlib.util

    validator = ROOT / "hooks" / "validate-schema.py"
    spec = importlib.util.spec_from_file_location("duckwork_seo_schema_validator", validator)
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_jsonld(content, filepath)


def validate_schema_result(
    tool_name: str = "", args: Any = None, result: Any = None, **_: Any
) -> str | None:
    """Append schema feedback after Duckwork file-write tools; never block writes."""
    targets = {
        "write_file": "path",
        "patch": "path",
        "skill_manage": "file_path",
    }
    if tool_name not in targets or not isinstance(args, dict) or not isinstance(result, str):
        return None
    raw_path = args.get(targets[tool_name])
    if not isinstance(raw_path, str) or Path(raw_path).suffix.lower() not in HTML_EXTENSIONS:
        return None
    path = Path(raw_path)
    try:
        if path.stat().st_size > 10 * 1024 * 1024:
            return None
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    findings = _validate_jsonld(content, str(path))
    if not findings:
        return None
    return result + "\n\nSEO schema validation feedback (the file was written):\n" + "\n".join(
        f"- {finding}" for finding in findings
    )


def _run_runtime(
    args: argparse.Namespace, *, env_overrides: dict[str, str] | None = None,
    capture_output: bool = False,
) -> int | subprocess.CompletedProcess[str]:
    if args.action == "show":
        target = (ROOT / args.path).resolve()
        try:
            target.relative_to(ROOT)
            print(target.read_text(encoding="utf-8"))
            return 0
        except (OSError, ValueError) as exc:
            print(f"Cannot read bundled file: {exc}")
            return 2
    from plugins.plugin_storage import plugin_data_dir

    env = _safe_child_env()
    if env_overrides:
        env.update(env_overrides)
    data_dir = plugin_data_dir("duckwork-seo")
    env["DUCKWORK_SEO_DATA_DIR"] = str(data_dir)
    env["DUCKWORK_SEO_CONFIG_DIR"] = str(data_dir / "config")
    env["DUCKWORK_SEO_CACHE_DIR"] = str(data_dir / "cache")
    command = [str(ROOT / "scripts" / "duckwork-seo"), args.action]
    if args.action == "setup" and args.skip_browser:
        command.append("--skip-browser")
    if args.action == "run":
        if args.extension:
            command.extend(["--extension", args.extension])
        command.extend([args.script, *args.script_args])
    elif args.action == "doctor" and args.json:
        command.append("--json")
    try:
        options = {"env": env, "check": False}
        if capture_output:
            options.update(capture_output=True, text=True, encoding="utf-8", errors="replace")
        if args.action != "run":
            options["cwd"] = ROOT
        result = subprocess.run(command, **options)
        return result if capture_output else result.returncode
    except OSError as exc:
        print(f"Could not start Duckwork SEO runtime: {exc}")
        return 2


def _run_scoped_tool(payload: dict[str, Any]) -> str:
    """Run one bundled utility with only secrets from this Duckwork profile."""
    script = payload.get("script")
    script_args = payload.get("args", [])
    extension = payload.get("extension")
    if not isinstance(script, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*\.py", script):
        return "Invalid script basename."
    if not isinstance(script_args, list) or not all(isinstance(item, str) for item in script_args):
        return "args must be a list of strings."
    if any(
        re.search(r"(?i)(api[-_]?key|(?:^|[-_])key(?:$|=)|token|password|secret|credential|authorization)", item)
        for item in script_args
    ):
        return "Pass credentials through the Duckwork profile vault, never as tool arguments."
    if extension is not None and extension != "banana":
        return "Unsupported extension."
    try:
        contract = _auth_contract()
        secret_names = contract.secrets_for(script, extension)
        names = secret_names | contract.profile_config_for(script, extension)
        if not names:
            return "This native tool runs only declared credentialed providers. Use the isolated CLI for offline utilities."
        from agent.secret_scope import get_secret

        scoped: dict[str, str] = {}
        for name in names:
            value = get_secret(name)
            if value:
                scoped[name] = str(value)
    except Exception:
        return "Duckwork profile secrets unavailable; no utility was started."
    try:
        from plugins.plugin_storage import plugin_data_dir

        runtime = _load_runtime()
        status = runtime._status(ROOT, Path(plugin_data_dir("duckwork-seo")))
        if not status["ready"]:
            return "Duckwork SEO runtime is not ready. Run `duckwork seo setup` and retry."
        script_path = runtime._resolve_script(ROOT, script, extension)
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        return f"Duckwork SEO utility unavailable: {exc}"
    env = runtime._safe_env(status)
    env.update(scoped)
    command = [str(status["python_path"]), str(script_path), *script_args]
    try:
        result = subprocess.run(
            command, env=env, capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=False, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "Duckwork SEO utility timed out after 120 seconds."
    except OSError as exc:
        return f"Duckwork SEO utility failed to launch: {exc}"
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    for name in secret_names:
        secret = scoped.get(name, "")
        if secret:
            stdout = stdout.replace(secret, "<redacted>")
            stderr = stderr.replace(secret, "<redacted>")
    redact_runtime = getattr(runtime, "_redact", None)
    if callable(redact_runtime):
        stdout = redact_runtime(stdout)
        stderr = redact_runtime(stderr)
    output = (stdout + ("\n" if stdout and stderr else "") + stderr).strip()
    return output or str(result.returncode)


def _setup_cli(subparser: argparse.ArgumentParser) -> None:
    actions = subparser.add_subparsers(dest="seo_action", required=True)
    setup = actions.add_parser("setup", help="Create the isolated Python environment and install dependencies")
    setup.add_argument("--skip-browser", action="store_true")
    setup.set_defaults(action="setup")
    doctor = actions.add_parser("doctor", help="Check runtime readiness")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(action="doctor")
    run = actions.add_parser("run", help="Run an allowlisted SEO utility")
    run.add_argument("--extension", choices=("banana",), help="Select an extension-specific bundled script")
    run.add_argument("script", help="Bundled script filename")
    run.add_argument("script_args", nargs=argparse.REMAINDER)
    run.set_defaults(action="run")
    show = actions.add_parser("show", help="Print a bundled reference or skill file")
    show.add_argument("path", help="Path relative to the plugin root")
    show.set_defaults(action="show")
    run.set_defaults(action="run")


def register(ctx: Any) -> None:
    """Register bundled skills, CLI runtime, and non-blocking result validation."""
    skills = ROOT / "skills"
    for child in sorted(skills.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.is_file():
            ctx.register_skill(child.name, skill_md)
    ctx.register_hook("transform_tool_result", validate_schema_result)
    ctx.register_tool(
        name="duckwork_seo_run",
        toolset="duckwork-seo",
        description="Run an allowlisted SEO utility using only secrets from the active Duckwork profile.",
        schema={
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "Bundled utility basename, for example moz_api.py."},
                "args": {"type": "array", "items": {"type": "string"}},
                "extension": {"type": "string", "enum": ["banana"]},
            },
            "required": ["script"],
            "additionalProperties": False,
        },
        handler=_run_scoped_tool,
    )
    ctx.register_cli_command(
        name="seo",
        help="Set up and run Duckwork SEO's isolated analysis tools",
        setup_fn=_setup_cli,
        handler_fn=_run_runtime,
        description="Run the Duckwork SEO runtime or read bundled references.",
    )
