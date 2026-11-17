# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def _command_stub(path: Path, name: str, message: str) -> None:
    target = path / name
    target.write_text(f'#!/bin/sh\nprintf "{message}:%s\\n" "$*"\n', encoding="utf-8")
    target.chmod(target.stat().st_mode | stat.S_IXUSR)


def test_install_script_installs_pypi_package_then_runs_setup(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "install-plugin.sh"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _command_stub(bin_dir, "python3", "pip")
    _command_stub(bin_dir, "duckwork-metronix-setup", "setup")

    syntax = subprocess.run(["/bin/bash", "-n", str(script)], capture_output=True, text=True, check=False)
    result = subprocess.run(
        ["/bin/bash", str(script), "--duckwork-home", "/tmp/duckwork"],
        capture_output=True,
        check=False,
        env={"PATH": str(bin_dir), "HOME": str(tmp_path)},
        text=True,
    )

    assert syntax.returncode == 0, syntax.stderr
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "pip:-m pip install --upgrade git+https://github.com/mtrnix/hermes-memory-metronix.git@main",
        "setup:--duckwork-home /tmp/duckwork",
    ]


def test_public_install_guides_use_configured_provider_flow() -> None:
    root = Path(__file__).resolve().parents[2]

    for guide in (root / "README.md", root / "docs" / "smoke.md", root / "TEST_PLAN.md"):
        content = guide.read_text(encoding="utf-8")
        assert "duckwork chat --memory-provider metronix" not in content
        assert "duckwork memory providers" not in content
