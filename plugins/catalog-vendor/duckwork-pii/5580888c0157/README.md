# duckwork-pii

Local PII detection for Duckwork Agent using `<PERSON>` and spaCy. No cloud service
or LLM is used for detection. This is a POC, not a confidentiality guarantee.

## Installation

Install the default English model, `en_core_web_sm` 3.8.0, separately in the
Python environment used by Duckwork before enabling the plugin. Duckwork admits
named PyPI dependencies only; the model wheel is hosted on GitHub and cannot be
installed through the plugin dependency installer. Use the interpreter from
Duckwork' managed environment (replace the path below):

```bash
uv pip install --python /path/to/duckwork/environment/bin/python https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
/path/to/duckwork/environment/bin/python -c "import spacy; spacy.load('en_core_web_sm')"
```

The plugin does not download models at runtime. If the model is missing,
redaction fails open and original text is sent to the provider.

For development:

```bash
uv venv --python 3.12 .venv
uv sync --frozen
uv pip install --python .venv/bin/python https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
```

For the existing directory-plugin symlink in a Duckwork profile, enable the plugin
through Duckwork so dependency admission provisions its managed environment:

```bash
env -u UV_NATIVE_TLS UV_SYSTEM_CERTS=true duckwork plugins enable duckwork-pii
```

Restart Duckwork after installing, updating code, or changing settings. The project
`.venv` is separate from Duckwork' managed environment. Do not install the plugin
both as a directory plugin and as an independently discovered pip entry point.

**Model licenses:** `en_core_web_sm` is MIT. The optional `it_core_news_sm` model
is CC BY-NC-SA 3.0; verify that its terms fit your use. The spaCy library has a
separate license.

## Request flow

1. `pre_llm_call` prepares one cached detector. It does not analyze or append user text.
2. `llm_request` redacts user prompt text in a copy of the provider request.
3. Duckwork continues its normal execution; original conversation history is unchanged.

Models load from installed packages or local directories. Runtime loading and
analysis never download models. Email recognition uses a bundled, offline suffix
snapshot. Overlapping detections are replaced across their full union.

## Settings

Settings live under `plugins.entries.duckwork-pii.settings` and are read once at
registration. Change them with `duckwork config set`, then restart Duckwork.

| Key | Default | Purpose |
|---|---|---|
| `language` | `en` | Language supported by the selected model |
| `model_name` | `en_core_web_sm` | Installed model name or local model directory |
| `score_threshold` | `0.4` | <PERSON> detection threshold |

The default model requires separate provisioning. To use Italian, first provision
`it_core_news_sm` 3.8.0 in the same Duckwork environment. The plugin does not
install or download it at runtime. Then set both Italian settings from the
command line:

```bash
duckwork config set plugins.entries.duckwork-pii.settings.language it
duckwork config set plugins.entries.duckwork-pii.settings.model_name it_core_news_sm
```

Restart Duckwork after changing settings. If the selected model is not installed,
initialization fails and the plugin's fail-open policy passes original text
through. Additional/custom models must be provisioned separately before use.

## Supported payloads

- Chat Completions text in messages with `role: user`.
- Responses string input and text in input messages with `role: user`.

System/developer prompts, Responses instructions, assistant messages, tool-call
arguments, and tool outputs are preserved and never analyzed. Messages without
an explicit user role are also preserved. Keys, roles, tool names, call IDs,
numeric values, schemas, images, audio, asset URLs, metadata, and unlisted
provider fields are not filtered. Names, places, organizations, email, phones, IBANs, cards, and
IP addresses are recognized; accuracy and false positives depend on context.

## Failure policy

**Fail-open:** a detector/import/model error returns the original text, including
any PII. Every later operation retries; there is no permanent failure latch.
Warnings contain only the exception class, never input, exception messages, or
tracebacks. The middleware's reason describes attempted fail-open filtering,
not a guarantee that every field was redacted.

Local history retains original values. No recovery mapping or value restoration
is implemented. Auxiliary calls, multimodal inputs, and middleware-bypassing paths
have not been verified end-to-end. This plugin must not be treated as a mandatory
privacy barrier. Use only synthetic data for development and smoke tests.

## Verification

```bash
.venv/bin/python -m unittest discover -s tests -v
duckwork plugins doctor . --ci
duckwork plugins validate . --json
uv pip check --python .venv/bin/python
```

Tests cover real offline detection, provider-payload rewriting, protocol preservation,
preparation without duplicate analysis, sanitized failures, and transient-error recovery.
The integration test uses a preinstalled model and forbids socket connections during
redaction. No remote LLM is contacted.
