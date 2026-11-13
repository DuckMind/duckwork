---
name: google-workspace
description: "Gmail, Calendar, Drive, Docs, Sheets via gws CLI or Python."
version: 1.2.1
author: Fordex
license: MIT
platforms: [linux, macos, windows]
setup_help: "Run duckwork skills setup google-workspace in the cron job's profile (use duckwork -p PROFILE skills setup google-workspace for a named profile); follow --client-secret, --auth-url, --auth-code-stdin, then --check. Do not disable readiness."
required_credential_files:
  - path: google_token.json
    description: Google OAuth2 token (created by setup script)
  - path: google_client_secret.json
    description: Google OAuth2 client credentials (downloaded from Google Cloud Console)
metadata:
  duckwork:
    tags: [Google, Gmail, Calendar, Drive, Sheets, Docs, Contacts, Email, OAuth]
    homepage: https://github.com/DuckMind/duckwork
    related_skills: [himalaya]
---

# Google Workspace

Gmail, Calendar, Drive, Contacts, Sheets, and Docs — through Duckwork-managed OAuth and a thin CLI wrapper. When `gws` is installed, the skill uses it as the execution backend for broader Google Workspace coverage; otherwise it falls back to the bundled Python client implementation.

## References

- `references/gmail-search-syntax.md` — Gmail search operators (is:unread, from:, newer_than:, etc.)
- `references/daily-brief.md` — daily/morning brief procedure: schedule + conflicts + meeting prep + urgent mail from Gmail and Calendar. Load it when the user asks for a morning brief, meeting preparation, or "what's on my calendar and what email needs attention."

## Scripts

- `scripts/setup.py` — OAuth2 setup (run once to authorize)
- `scripts/google_api.py` — compatibility wrapper CLI. It prefers `gws` for operations when available, while preserving Duckwork' existing JSON output contract.

## First-Time Setup

Use the product command, not ambient `python` or a copied `setup.py` path.
It runs the trusted bundled setup in Duckwork's current runtime, including
bytecode-only distributions. No community/installed skill script is executed.

```bash
duckwork skills setup google-workspace
```

Without an option this only reports credential-file presence and recovery steps:
no network, browser, token refresh, package install or file write. Missing files
remain a setup-needed failure. Select the **cron job's profile** for every step:
`duckwork -p PROFILE skills setup google-workspace`. For a custom home, preserve
its `DUCKWORK_HOME` as well. The command prints the home it checks.

For the examples below, this POSIX-shell shorthand selects the default profile;
replace `default` with the cron job's profile. In PowerShell, type the full command.

```bash
GSETUP="duckwork -p default skills setup google-workspace"
```

### Step 0: Validate existing authorization

```bash
$GSETUP --check
```

This may refresh an expired token. `AUTHENTICATED` checks token validity, not
whether every requested service/API or the scheduled workload will succeed.
`AUTHENTICATED (partial)` means some permissions are absent. `--check-live`
explicitly makes a Calendar API request; it is never run automatically.

### Step 1: Confirm the requested permissions

This setup currently requests the builtin's **full** scope set: Gmail read,
send and modify; Calendar; Drive; Contacts read-only; Sheets; Docs. Explain these
permissions and obtain the user's approval **before** `--auth-url`.
`--services` and `--format` are not supported. Do not silently substitute full
access when the user requested a narrower set. If they decline, stop and choose
an appropriately scoped integration instead. Partial consent can leave some
commands unavailable; never claim that file presence grants permissions.

### Step 2: Create OAuth credentials

Ask the user to create/select a Google Cloud project, enable the APIs they intend
to use, configure the OAuth consent screen, and create a **Desktop app** OAuth
client. If the app is in Testing, add their account as a test user. Download the
client JSON locally; do not paste client secrets into chat or logs. Workspace
policy or Advanced Protection may require administrator approval.

```bash
$GSETUP --client-secret "/path/to/client_secret.json"
```

Keep this file private. It is stored as `google_client_secret.json` inside the
active profile home, not in the application installation.

### Step 3: Generate the consent URL

```bash
$GSETUP --auth-url
```

Output is a plain URL, **not JSON**. Send the exact URL to the user, who must open
it and approve consent themselves. After approval the browser may fail to load
`http://localhost:1`; this is expected for the manual redirect flow. Copy the
entire redirected URL from the address bar. Pending PKCE state/verifier are
stored in `google_oauth_pending.json` in this same profile. A new `--auth-url`
replaces the pending session, so use only the newest redirect.

### Step 4: Exchange the authorization response

In the user's local terminal:

```bash
$GSETUP --auth-code-stdin
```

Paste the full redirect URL at the hidden prompt. Raw codes are also accepted.
For automation, supply the response over stdin, not a command argument or shell
history entry. Never request that users paste codes/tokens into public chat.
If the code expired, was already used, or came from an older tab, rerun
`--auth-url` explicitly and repeat consent. No fresh URL is generated automatically.

### Step 5: Verify and allow cron to recheck

```bash
$GSETUP --check
```

The token is stored in `google_token.json` in the active profile and can refresh
automatically when used. Pending PKCE state is removed after a successful
exchange. `gws`, when used, receives that same profile's token file.

Cron must remain blocked while required files are missing. It rechecks on the
next dispatch; setup does not run the job or clear its historical last-run status.
Check that the cron process and setup report the same profile/home. Do not remove
the skill or disable readiness just to make the error disappear.

If Google dependencies are unavailable, `--install-deps` explicitly syncs the
Google extra through Duckwork PM; restart Duckwork afterward. Do not use pip or
another Python environment. To revoke authorization explicitly: `$GSETUP --revoke`.

## Usage

All commands go through the API script. Set `GAPI` as a shorthand:

```bash
GAPI="python ${DUCKWORK_HOME:-$HOME/.duckwork}/skills/productivity/google-workspace/scripts/google_api.py"
```

### Gmail

```bash
# Search (returns JSON array with id, from, subject, date, snippet)
$GAPI gmail search "is:unread" --max 10
$GAPI gmail search "from:boss@company.com newer_than:1d"
$GAPI gmail search "has:attachment filename:pdf newer_than:7d"

# Read full message (returns JSON with body text)
$GAPI gmail get MESSAGE_ID

# Send
$GAPI gmail send --to user@example.com --subject "Hello" --body "Message text"
$GAPI gmail send --to user@example.com --subject "Report" --body "<h1>Q4</h1><p>Details...</p>" --html
$GAPI gmail send --to user@example.com --subject "Hello" --from '"Research Agent" <user@example.com>' --body "Message text"

# Reply (automatically threads and sets In-Reply-To)
$GAPI gmail reply MESSAGE_ID --body "Thanks, that works for me."
$GAPI gmail reply MESSAGE_ID --from '"Support Bot" <user@example.com>' --body "Thanks"

# Labels
$GAPI gmail labels
$GAPI gmail modify MESSAGE_ID --add-labels LABEL_ID
$GAPI gmail modify MESSAGE_ID --remove-labels UNREAD
```

### Calendar

```bash
# List events (defaults to next 7 days)
$GAPI calendar list
$GAPI calendar list --start 2026-03-01T00:00:00Z --end 2026-03-07T23:59:59Z

# Create event (ISO 8601 with timezone required)
$GAPI calendar create --summary "Team Standup" --start 2026-03-01T10:00:00-06:00 --end 2026-03-01T10:30:00-06:00
$GAPI calendar create --summary "Lunch" --start 2026-03-01T12:00:00Z --end 2026-03-01T13:00:00Z --location "Cafe"
$GAPI calendar create --summary "Review" --start 2026-03-01T14:00:00Z --end 2026-03-01T15:00:00Z --attendees "alice@co.com,bob@co.com"

# Delete event
$GAPI calendar delete EVENT_ID
```

### Drive

```bash
# Search existing files
$GAPI drive search "quarterly report" --max 10
$GAPI drive search "mimeType='application/pdf'" --raw-query --max 5

# Get metadata for a single file
$GAPI drive get FILE_ID

# Upload a local file (auto-detects MIME type)
$GAPI drive upload /path/to/report.pdf
$GAPI drive upload /path/to/image.png --name "Logo.png" --parent FOLDER_ID

# Download (binary files download as-is; Google-native files export to a
# sensible default — Docs→pdf, Sheets→csv, Slides→pdf, Drawings→png)
$GAPI drive download FILE_ID
$GAPI drive download DOC_ID --output ~/doc.pdf
$GAPI drive download DOC_ID --export-mime text/plain --output ~/doc.txt

# Create a folder
$GAPI drive create-folder "Reports"
$GAPI drive create-folder "Q4" --parent FOLDER_ID

# Share
$GAPI drive share FILE_ID --email alice@example.com --role reader
$GAPI drive share FILE_ID --email alice@example.com --role writer --notify
$GAPI drive share FILE_ID --type anyone --role reader        # anyone with link
$GAPI drive share FILE_ID --type domain --domain example.com --role reader

# Delete — defaults to trash (reversible). Use --permanent to skip the trash.
$GAPI drive delete FILE_ID
$GAPI drive delete FILE_ID --permanent
```

### Contacts

```bash
$GAPI contacts list --max 20
```

### Sheets

```bash
# Create a new spreadsheet
$GAPI sheets create --title "Q4 Budget"
$GAPI sheets create --title "Inventory" --sheet-name "Stock"

# Read
$GAPI sheets get SHEET_ID "Sheet1!A1:D10"

# Write
$GAPI sheets update SHEET_ID "Sheet1!A1:B2" --values '[["Name","Score"],["Alice","95"]]'

# Append rows
$GAPI sheets append SHEET_ID "Sheet1!A:C" --values '[["new","row","data"]]'
```

### Docs

```bash
# Read (a tabbed Doc returns a "tabs" array; single-tab and legacy Docs also return "body")
$GAPI docs get DOC_ID
$GAPI docs get DOC_ID --tab TAB_ID     # read one tab of a tabbed Doc

# Create a new Doc (optionally seeded with body text)
$GAPI docs create --title "Meeting Notes"
$GAPI docs create --title "Draft" --body "First paragraph..."

# Append text to the end of an existing Doc
$GAPI docs append DOC_ID --text "Additional content to append"
$GAPI docs append DOC_ID --tab TAB_ID --text "..."   # --tab required when the Doc has multiple tabs
```

## Output Format

All commands return JSON. Parse with `jq` or read directly. Key fields:

- **Gmail search**: `[{id, threadId, from, to, subject, date, snippet, labels}]`
- **Gmail get**: `{id, threadId, from, to, subject, date, labels, body}`
- **Gmail send/reply**: `{status: "sent", id, threadId}`
- **Calendar list**: `[{id, summary, start, end, location, description, htmlLink}]`
- **Calendar create**: `{status: "created", id, summary, htmlLink}`
- **Drive search**: `[{id, name, mimeType, modifiedTime, webViewLink}]`
- **Drive get**: `{id, name, mimeType, modifiedTime, size, webViewLink, parents, owners}`
- **Drive upload**: `{status: "uploaded", id, name, mimeType, webViewLink}`
- **Drive download**: `{status: "downloaded", id, name, path, mimeType}`
- **Drive create-folder**: `{status: "created", id, name, webViewLink}`
- **Drive share**: `{status: "shared", permissionId, fileId, role, type}`
- **Drive delete**: `{status: "trashed" | "deleted", fileId, permanent}`
- **Contacts list**: `[{name, emails: [...], phones: [...]}]`
- **Sheets get**: `[[cell, cell, ...], ...]`
- **Sheets create**: `{status: "created", spreadsheetId, title, spreadsheetUrl}`
- **Docs create**: `{status: "created", documentId, title, url}`
- **Docs append**: `{status: "appended", documentId, inserted_at, characters}`

## Rules

1. **Never send email, create/delete calendar events, delete Drive files, share files, or modify Docs/Sheets without confirming with the user first.** Show what will be done (recipients, file IDs, content, share role) and ask for approval. For `drive delete`, prefer the default trash (reversible) over `--permanent`.
2. **Check auth before first use** — run `duckwork skills setup google-workspace --check`. If it fails, guide the user through setup.
3. **Use the Gmail search syntax reference** for complex queries — load it with `skill_view("google-workspace", file_path="references/gmail-search-syntax.md")`.
4. **Calendar times must include timezone** — always use ISO 8601 with offset (e.g., `2026-03-01T10:00:00-06:00`) or UTC (`Z`).
5. **Respect rate limits** — avoid rapid-fire sequential API calls. Batch reads when possible.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `NOT_AUTHENTICATED` | Run setup Steps 2-5 above |
| `REFRESH_FAILED` | Token revoked or expired — redo Steps 3-5 |
| `HttpError 403: Insufficient Permission` | Missing API scope — `$GSETUP --revoke` then redo Steps 3-5 |
| `AUTHENTICATED (partial)` or "Token missing scopes" | New write capabilities (Drive write/delete, Docs create/edit) require re-authorization. `$GSETUP --revoke` then redo Steps 3-5 to grant the upgraded scopes. |
| `HttpError 403: Access Not Configured` | API not enabled — user needs to enable it in Google Cloud Console |
| `ModuleNotFoundError` | Run `$GSETUP --install-deps` |
| Advanced Protection blocks auth | Workspace admin must allowlist the OAuth client ID |

## Revoking Access

```bash
$GSETUP --revoke
```
