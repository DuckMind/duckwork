from __future__ import annotations

import argparse
import getpass
import importlib.metadata
import os
import secrets
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mpp.methods.tempo import TempoAccount

from .httpx import _parse_origins


def _duckwork_home() -> Path:
    return Path(os.environ.get("DUCKWORK_HOME", Path.home() / ".duckwork")).expanduser()


def _bin(directory: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return directory / f"{name}{suffix}"


@dataclass(frozen=True)
class DuckworkInstallation:
    python: Path
    duckwork: Path


def _has_duckwork(python: Path) -> bool:
    if not python.is_file():
        return False
    try:
        result = subprocess.run(
            [str(python), "-c", "import duckwork_cli"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _from_python(python: Path) -> DuckworkInstallation | None:
    python = python.expanduser().absolute()
    duckwork = _bin(python.parent, "duckwork")
    if duckwork.is_file() and _has_duckwork(python):
        return DuckworkInstallation(python, duckwork)
    return None


def _from_duckwork(duckwork: Path) -> DuckworkInstallation | None:
    resolved = duckwork.expanduser().resolve()
    return _from_python(_bin(resolved.parent, "python"))


def _duckwork_installation(home: Path, override: str | None = None) -> DuckworkInstallation:
    explicit = override or os.environ.get("DUCKWORK_PYTHON")
    if explicit:
        installation = _from_python(Path(explicit))
        if installation is None:
            raise SystemExit(f"Duckwork is not installed for Python: {explicit}")
        return installation

    command = shutil.which("duckwork")
    candidates = []
    if command:
        candidates.append(_from_duckwork(Path(command)))

    scripts = "Scripts" if os.name == "nt" else "bin"
    candidates.append(_from_python(_bin(home / "duckwork-agent" / "venv" / scripts, "python")))
    if os.name != "nt":
        candidates.append(_from_python(Path("/usr/local/lib/duckwork-agent/venv/bin/python")))

    for installation in candidates:
        if installation is not None:
            return installation
    raise SystemExit(
        "Duckwork is not installed. Install Duckwork or pass --duckwork-python PATH."
    )


def _env_key(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("TEMPO_PRIVATE_KEY="):
            return line.partition("=")[2].strip().strip("'\"") or None
    return None


def _write_env(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [line for line in lines if not line.startswith(f"{key}=")]
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write("\n".join([*lines, f"{key}={value}"]) + "\n")
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _wallet(env_file: Path) -> TempoAccount:
    private_key = _env_key(env_file) or os.environ.get("TEMPO_PRIVATE_KEY", "").strip()
    if not private_key:
        private_key = getpass.getpass(
            "Tempo private key (leave blank to generate a new wallet): "
        ).strip()
    if not private_key:
        private_key = "0x" + secrets.token_hex(32)
    try:
        account = TempoAccount.from_key(private_key)
    except Exception as error:
        raise SystemExit("Invalid Tempo private key.") from error

    _write_env(env_file, "TEMPO_PRIVATE_KEY", private_key)
    return account


def install(
    python_override: str | None = None,
    *,
    allowed_origins: list[str] | None = None,
) -> None:
    if allowed_origins is not None:
        try:
            _parse_origins(allowed_origins)
        except (TypeError, ValueError) as error:
            raise SystemExit(str(error)) from None
    home = _duckwork_home()
    installation = _duckwork_installation(home, python_override)
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is required to install duckwork-mpp.")

    package = f"duckwork-mpp=={importlib.metadata.version('duckwork-mpp')}"
    subprocess.run(
        [uv, "pip", "uninstall", "--python", str(installation.python), "mpp-duckwork"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [uv, "pip", "install", "--python", str(installation.python), package], check=True
    )
    env_file = home / ".env"
    account = _wallet(env_file)
    if allowed_origins is not None:
        _write_env(env_file, "MPP_ALLOWED_ORIGINS", ",".join(allowed_origins))
    subprocess.run(
        [str(installation.duckwork), "plugins", "enable", "mpp", "--no-allow-tool-override"],
        check=True,
        env={**os.environ, "DUCKWORK_HOME": str(home)},
    )
    print(f"Installed duckwork-mpp. Wallet: {account.address}")


def uninstall(python_override: str | None = None) -> None:
    home = _duckwork_home()
    installation = _duckwork_installation(home, python_override)
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is required to uninstall duckwork-mpp.")

    subprocess.run(
        [str(installation.duckwork), "plugins", "disable", "mpp"],
        check=True,
        env={**os.environ, "DUCKWORK_HOME": str(home)},
    )
    subprocess.run(
        [uv, "pip", "uninstall", "--python", str(installation.python), "duckwork-mpp"],
        check=True,
    )
    print("Uninstalled duckwork-mpp. The wallet remains in Duckwork's .env file.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage duckwork-mpp for Duckwork Agent.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("install", "Install into Duckwork and configure a wallet."),
        ("uninstall", "Disable and remove duckwork-mpp from Duckwork."),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument(
            "--duckwork-python",
            metavar="PATH",
            help="Python executable used by Duckwork (or set DUCKWORK_PYTHON).",
        )
        if command == "install":
            command_parser.add_argument(
                "--allowed-origin",
                action="append",
                metavar="ORIGIN",
                help="Exact origin allowed to charge the wallet; repeat to allow more than one.",
            )
    args = parser.parse_args()
    if args.command == "install":
        install(args.duckwork_python, allowed_origins=args.allowed_origin)
    else:
        uninstall(args.duckwork_python)


if __name__ == "__main__":
    main()
