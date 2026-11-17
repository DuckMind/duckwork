"""Install the Desktop plugin and its credential-safe HTTP backend."""
from __future__ import annotations

import os
from pathlib import Path
import shutil


def install(home: Path | None = None) -> Path:
    source = Path(__file__).resolve().parent
    target_home = Path(home) if home is not None else Path(
        os.environ.get('DUCKWORK_HOME', Path.home() / '.duckwork'))
    package = target_home / 'plugins' / 'duckwork-slash-router'
    desktop_copy = target_home / 'desktop-plugins' / 'duckwork-slash-router'
    conflicts = [path for path in (package, desktop_copy)
                 if path.exists() or path.is_symlink()]
    if conflicts:
        existing = ', '.join(str(path) for path in conflicts)
        raise FileExistsError(
            f'Existing plugin installation(s): {existing}. '
            'Back them up and remove them manually before installing the Desktop package; '
            'this installer will not replace or migrate them.')
    package.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, package, ignore=shutil.ignore_patterns(
        '.git', '.gitignore', '.github', '__pycache__', '*.py[cod]', 'tests',
        'install.py', 'live-results.json', 'videos', 'node_modules'))
    return package


def main() -> None:
    package = install()
    print(f'Installed Duckwork Desktop plugin: {package}')
    print('Enable its HTTP backend with: duckwork plugins enable duckwork-slash-router')
    print('Rescan or reload Duckwork Desktop, then enable Slash Router in Capabilities → Plugins.')
    print('Hosted Duckwork installs prompt for TYPESAFE_API_KEY; this local installer does not handle secrets.')


if __name__ == '__main__':
    main()
