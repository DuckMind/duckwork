# mnemostack (compatibility shim)

This directory is what duckwork-agent **0.19** scans for; it does not contain the
provider. The implementation lives in the `duckwork-mnemostack` package on PyPI.

Do not copy it by hand — `duckwork-mnemostack install` puts it in the right place
for the *active* Duckwork profile and verifies that duckwork can actually load it:

```bash
pip install duckwork-mnemostack
duckwork-mnemostack install
duckwork memory setup mnemostack
```

On duckwork-agent **0.20 and later** the pip entry point is discovered on its own
and this directory is unnecessary (harmless if present — a directory plugin
takes precedence over an entry point, and both resolve to the same provider).

See the project README for configuration, and SECURITY.md for what leaves the
machine.
