# Hopper

**Hopper by @mykeura adds and manages custom OpenRouter models in Duckwork without modifying the built-in catalog.**

![Hopper for Duckwork](images/hopper.jpg)

Hopper gives you a small, personal OpenRouter catalog that you can edit from the command line. It can contain free models while they are temporarily available, as well as paid models available through OpenRouter. Model availability and pricing are controlled by OpenRouter and may change.

## Default models

Hopper v1.4.0 starts with this model:

```text
inclusionai/ling-3.0-flash-vl:free
```

Ling 3.0 Flash VL is the recommended starting point for now: a multimodal
model that does not collect data, served via OpenRouter from NovitaAI
servers. It is currently free with limited usage.

## Manage models

Hopper stores its catalog in a single text file under your Duckwork home
directory:

| OS | Duckwork home | Models file |
|----|-------------|-------------|
| Linux / macOS | `~/.duckwork` | `~/.duckwork/plugin-data/hopper/models.txt` |
| Windows | `%USERPROFILE%\.duckwork` | `%USERPROFILE%\.duckwork\plugin-data\hopper\models.txt` |

If you set the `DUCKWORK_HOME` environment variable, that path is used instead
of the defaults above. You can also point Hopper at a specific catalog with
`HOPPER_MODELS_FILE`.

### With the CLI (recommended)

The bundled helper lives at `<duckwork home>/plugins/hopper/manage.py`.

**Linux / macOS:**

```bash
python3 ~/.duckwork/plugins/hopper/manage.py list
python3 ~/.duckwork/plugins/hopper/manage.py add "provider/model-id"
python3 ~/.duckwork/plugins/hopper/manage.py remove "provider/model-id"
python3 ~/.duckwork/plugins/hopper/manage.py reset
python3 ~/.duckwork/plugins/hopper/manage.py file
```

**Windows (PowerShell):**

```powershell
py "$env:USERPROFILE\.duckwork\plugins\hopper\manage.py" list
py "$env:USERPROFILE\.duckwork\plugins\hopper\manage.py" add "provider/model-id"
py "$env:USERPROFILE\.duckwork\plugins\hopper\manage.py" remove "provider/model-id"
py "$env:USERPROFILE\.duckwork\plugins\hopper\manage.py" reset
py "$env:USERPROFILE\.duckwork\plugins\hopper\manage.py" file
```

**Windows (CMD):**

```bat
py "%USERPROFILE%\.duckwork\plugins\hopper\manage.py" list
py "%USERPROFILE%\.duckwork\plugins\hopper\manage.py" add "provider/model-id"
py "%USERPROFILE%\.duckwork\plugins\hopper\manage.py" remove "provider/model-id"
py "%USERPROFILE%\.duckwork\plugins\hopper\manage.py" reset
py "%USERPROFILE%\.duckwork\plugins\hopper\manage.py" file
```

Commands:

| Command | What it does |
|---------|----------------|
| `list` | Print the configured model IDs |
| `add "provider/model-id" …` | Add one or more OpenRouter model IDs |
| `remove "provider/model-id" …` | Remove one or more OpenRouter model IDs |
| `reset` | Restore the bundled default model |
| `file` | Print the full path to `models.txt` |

On Windows, use `python` instead of `py` if the Python launcher is not
installed.

### Editing the file directly

Open the models file from the table above (or run the `file` command to print
its exact location) in any text editor:

- One OpenRouter model ID per line (`provider/model-id` or
  `provider/model-id:free`).
- Blank lines are ignored.
- Lines starting with `#` are comments.
- Duplicate IDs are saved once.
- An empty catalog is valid: it hides every Hopper model.

Save the file, then reopen the Duckwork model picker (or press **Refresh
models** in the selector) so the updated catalog appears. After removing a
model, restart Duckwork Desktop as well; otherwise removed models keep
appearing until that refresh.

Hopper uses your normal `OPENROUTER_API_KEY`.

## Install or upgrade

Copy this directory to `~/.duckwork/plugins/hopper` (or install it with
`duckwork plugins install owner/repo`), then:

1. Restart Duckwork (or its gateway).
2. Open **Capabilities → Plugins** and click **Rescan**.
3. Confirm Hopper is listed as a model provider.
4. Choose a Hopper model from the Duckwork model selector.

Your existing model list (`~/.duckwork/plugin-data/hopper/models.txt`) is kept
on upgrade.

## A small way to support the project

If you are considering the Fordex Portal Personal plan, you can use [my Fordex Portal referral link](https://portal.fordex.com/r/mykeura). It takes **$15 off your first month** and gives me a **$10 referral credit** that helps cover the API usage behind my ongoing work on Hopper and related Duckwork plugins. It is entirely optional, but it is a simple way for both of us to benefit.

The offer is for new customers starting a new Personal subscription. It applies to the first invoice, and each payment card can be used for only one referral; if the card has already backed another referral, the discount is reversed and no referral reward is paid.

## License

MIT License.

Duckwork Agent and OpenRouter are separate projects/services. Hopper is an independent plugin and is not affiliated with or endorsed by Fordex, OpenRouter, or InclusionAI.
