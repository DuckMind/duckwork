# THEIA Computer Use installed

**THEIA — The Human Environment Intelligence Aperture** is installed.

Next steps:

```powershell
duckwork plugins enable duckwork-windows-computer-use
duckwork tools enable windows_computer_use
python scripts/doctor.py
```

Restart Duckwork after enabling the plugin/toolset.

## Basic dependencies

Current Duckwork Agent plugin installers read THEIA's `pip_dependencies` metadata
from `plugin.yaml` and/or the top-level `requirements.txt`, then install the
lightweight basic dependencies into the Python environment currently running
Duckwork Agent. THEIA also keeps a best-effort first-load fallback for older
Duckwork builds or blocked installs.

This covers PyAutoGUI, Pillow, PyGetWindow, python3-xlib on Linux only, and
pywin32 on Windows only. If Duckwork is running from a non-writable system Python,
the first-load fallback also tries `python -m pip install --user -r
requirements.txt`.

If auto-install is disabled or blocked, run from the installed plugin directory:

```powershell
python scripts/doctor.py --install-basic
python -m pip install --user -r requirements.txt
```

## LocateAnything visual grounding

THEIA uses LocateAnything visual grounding by default for `computer_use_locate`
and `computer_use_find_click`. Heavy ML/CUDA packages are intentionally installed
into an isolated worker venv outside Duckwork, not into the live Duckwork Python
environment. Basic screenshot, coordinate, pixel, mouse, and keyboard tools stay
available as the fallback while the worker installs or if it is unavailable.

Manual eager setup or repair:

```powershell
python scripts/setup_locate_worker.py --torch auto
python scripts/doctor.py --install-locate --locate
```

Set `THEIA_AUTO_INSTALL_BASIC_DEPS=false` or
`THEIA_AUTO_INSTALL_LOCATE_WORKER=false` to disable automatic dependency setup in
audited or air-gapped environments.
