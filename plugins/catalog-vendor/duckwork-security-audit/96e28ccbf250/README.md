# Duckwork Security Audit

A small security-audit plugin for [Duckwork Agent](https://github.com/DuckMind/duckwork).

It gives Duckwork one approval-gated `security_audit` tool for local **secret scanning**, **dependency vulnerability scanning**, and **static analysis** using:

- **Gitleaks** for leaked secrets and credentials in the current workspace tree
- **OSV-Scanner** for vulnerable dependencies
- **Semgrep CE** for static-analysis findings

I built this because I wanted Duckwork to be able to run the same security check I use before calling a coding task finished, without handing the model a pile of shell commands or letting scans happen silently in the background.

## What it does differently

The plugin is intentionally pretty boring about security:

- Duckwork asks for **human approval before every audit**.
- Scanner commands are launched with `shell=False`.
- The plugin does not edit the project being scanned.
- Missing tools, timeouts, malformed output, partial Semgrep analysis errors, and unexpected scanner failures are reported as incomplete coverage instead of quietly becoming a pass.
- Gitleaks runs with full redaction, and secret values are never copied into the normalized result.
- Scanner output is bounded while the process is running instead of being allowed to grow without limit in memory.
- Child processes get a cleaned-up environment so Duckwork Desktop / Python / terminal variables do not interfere with scanner JSON output.

The final result uses `PASS`, `FAIL`, `NOT_APPLICABLE`, `UNRESOLVED`, or `BLOCKED`, so the agent can tell the difference between "clean" and "I could not verify this."

## Tested with

The first real-world test setup was:

- Duckwork Agent `v2026.9.14` / Agent `v0.21.3`
- Windows 11
- Duckwork' Python 3.11 runtime

The code itself is platform-neutral, and the test suite runs on Windows and Linux.

## Requirements

Install these separately and make sure they are on `PATH`:

- [Gitleaks](https://github.com/gitleaks/gitleaks)
- [OSV-Scanner](https://github.com/google/osv-scanner)
- [Semgrep CE](https://github.com/semgrep/semgrep)

There are no third-party Python dependencies in the plugin itself, and Duckwork does not need to be patched.

## Install

### Recommended: let Duckwork install it from GitHub

Run this in **PowerShell, Command Prompt, Windows Terminal, or a normal macOS/Linux shell**—anywhere the `duckwork` command works:

```bash
duckwork plugins install dafka007/duckwork-security-audit --enable
```

You do **not** need to download the repository yourself when using this command; Duckwork fetches the plugin from GitHub and installs it into its plugin area.

Restart Duckwork after installation.

### Reproducible install

Duckwork also supports pinning a custom plugin to one exact immutable Git commit. Replace `<FULL_COMMIT_SHA>` with the full 40-character commit SHA from the release you want:

```bash
duckwork plugins install dafka007/duckwork-security-audit --enable --ref <FULL_COMMIT_SHA>
```

Duckwork intentionally requires a full commit SHA for `--ref`; tags, branches, and abbreviated SHAs are not accepted for pinned installs.

### Manual download

If you prefer not to use the installer command, GitHub's **Releases** page provides source ZIP and TAR.GZ downloads. The repository's **Code → Download ZIP** option also works for the current branch.

Extract the repository and place the folder at:

```text
~/.duckwork/plugins/duckwork-security-audit/
```

On a normal Windows setup, `~` means your user profile folder, so that is typically equivalent to:

```text
%USERPROFILE%\.duckwork\plugins\duckwork-security-audit\
```

Then enable the plugin and restart Duckwork:

```bash
duckwork plugins enable duckwork-security-audit
```

To check that Duckwork can discover and load it:

```bash
duckwork plugins doctor ~/.duckwork/plugins/duckwork-security-audit --ci
```

## Usage

Ask Duckwork to call the tool with the workspace you want checked. For example:

```text
Use only the security_audit tool.
Run a security audit on exactly this workspace:
C:\path\to\project
```

Duckwork should show an approval prompt before any scanner starts.

A clean result looks roughly like this:

```json
{
  "type": "SECURITY_AUDIT",
  "overall": "PASS",
  "coverage_incomplete": false,
  "scanners": {
    "gitleaks": {"status": "PASS", "findings": []},
    "osv": {"status": "NOT_APPLICABLE", "findings": []},
    "semgrep": {"status": "PASS", "findings": []}
  }
}
```

OSV-Scanner exit code `128` is treated as `NOT_APPLICABLE`; OSV documents that code as "no packages found."

### Gitleaks scope

The plugin currently uses Gitleaks' `dir` scan mode. That checks the files in the workspace tree being audited; it does **not** scan the repository's full Git commit history. Historical secret scanning may be added separately in the future so it can have its own scope and performance expectations.

## Configuration

Normally the plugin just uses the scanner executables found on `PATH`. These environment variables are available when you need something different:

| Variable | Purpose |
| --- | --- |
| `HSA_GITLEAKS` | Gitleaks executable path/name |
| `HSA_OSV_SCANNER` | OSV-Scanner executable path/name |
| `HSA_SEMGREP` | Semgrep executable path/name |
| `HSA_SEMGREP_CONFIG` | Semgrep rules/config source; defaults to `auto` |
| `HSA_TIMEOUT_SECONDS` | Per-scanner timeout, 10–1800 seconds; default 300 |

For example, to use a local Semgrep rules directory on Windows:

```powershell
$env:HSA_SEMGREP_CONFIG = "C:\security\semgrep-rules"
```

### Network/privacy note

The plugin itself does not upload your source code, but the scanners have their own behavior:

- Gitleaks runs locally.
- OSV-Scanner may contact vulnerability/package services depending on its configuration.
- Semgrep's default `auto` config may download rules and may use Semgrep metrics according to Semgrep's own settings. The plugin preserves `SEMGREP_SEND_METRICS`, `SEMGREP_APP_TOKEN`, and `SEMGREP_URL` if you have set them.

If you want Semgrep to use only local rules, point `HSA_SEMGREP_CONFIG` at a local rules file/directory and configure Semgrep's own network/metrics settings the way you want them.

## Result meanings

- **PASS** — scanner ran successfully and found nothing.
- **FAIL** — scanner ran and reported one or more findings.
- **NOT_APPLICABLE** — there was nothing relevant for that scanner to inspect.
- **UNRESOLVED** — coverage could not be trusted (missing scanner, timeout, malformed output, incomplete scanner analysis, unexpected scanner error, etc.).
- **BLOCKED** — the workspace itself could not be validated.

Overall precedence is `FAIL` → `UNRESOLVED` → `PASS`. A `FAIL` result can still set `coverage_incomplete: true` when a scanner found real findings but also reported partial analysis errors.

## What v1 does not do

- It does not install or update scanners for you.
- It does not auto-fix findings.
- It does not scan full Git history with Gitleaks.
- It does not do ZAP/DAST scanning. Active web scanning has a different safety/authorization model and should be an explicit feature if it is added later.
- It does not replace Duckwork' own dependency/supply-chain security commands.

## Development

The tests do not need the scanners installed; scanner processes are mocked except for one small bounded-output subprocess regression test.

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
```

Pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
