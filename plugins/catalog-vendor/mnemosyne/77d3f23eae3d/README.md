# Mnemosyne for the Duckwork plugin catalog

This directory is the Duckwork **directory plugin** that the catalog installs
(`duckwork plugins install mnemosyne-memory`). It is a thin wrapper:

- `plugin.yaml` names the plugin `mnemosyne`, marks it `kind: exclusive` (a
  memory provider, loaded only when `memory.provider: mnemosyne` is set), and
  requires the first Duckwork release that carries the whole catalog path
  (`requires_duckwork: ">=0.21.4"`: declared Python dependencies installed and
  re-applied after `duckwork update`, plus memory providers that leave core
  installed from the catalog automatically). Both landed after 0.21.3, so
  0.21.4 is a floor, not a round number.
- `pyproject.toml` declares the real implementation, the `mnemosyne-duckwork`
  package on PyPI, plus `mnemosyne-memory[embeddings]`. Duckwork installs both
  into its own venv on install and re-applies them after every `duckwork update`.
- `__init__.py` re-exports `register` and `register_memory_provider` from
  the installed package so the directory is loadable.

The package itself lives in `../duckwork/` and is released to PyPI from there.
Nothing in this directory is imported by the package or its tests.

## Wrapper installs

Existing wrapper-mode installs (`mnemosyne-duckwork install --mode wrapper`)
also live at `$DUCKWORK_HOME/plugins/mnemosyne`. The two are the same plugin
name on purpose: a machine has one or the other, and a catalog install onto
an existing wrapper is refused by Duckwork with "already exists" rather than
silently replacing it. Remove the wrapper first if you want to switch.
