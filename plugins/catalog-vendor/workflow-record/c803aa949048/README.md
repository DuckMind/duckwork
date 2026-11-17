# Workflow Record

> **Labs plugin: works, but unsupported.** Fordex built it and does not maintain it. See
> [what "labs" means](../README.md#what-labs-means).

`duckwork record` lets you show Duckwork a browser workflow instead of describing it. It attaches to
your Chromium-family browser (Chrome, Chromium, Brave, Edge) over the DevTools protocol, watches
what you do in the active tab, and saves the demonstration as a JSON recording. A bundled skill
then tells `/learn` how to turn that recording into a skill that replays the flow with Duckwork'
browser tools.

```
record  ->  /learn  ->  replay
```

## Install

```bash
duckwork plugins install workflow-record
```

It adds one CLI command (`duckwork record`) and one skill (`workflow-record:replay-recording`). No
model tools, no hooks, nothing runs during chats. The only dependency is `websockets`, which Duckwork
already ships.

## Record

1. Start a browser Duckwork can reach over CDP. Any of these works:
   - in a Duckwork chat, `/browser connect` (launches Chrome with remote debugging on port 9222), or
   - start it yourself: `google-chrome --remote-debugging-port=9222 --user-data-dir=<dir>`, or
   - point Duckwork at an existing endpoint with `browser.cdp_url` in `config.yaml`.
2. Open the page where the workflow starts and keep that tab in front.
3. Run:

   ```bash
   duckwork record --slug shop-login
   ```

4. Do the workflow in the browser, then press `Ctrl-C` in the terminal. Duckwork saves the recording
   and prints the next step.

The endpoint is taken from `--cdp URL`, else `BROWSER_CDP_URL`, else `browser.cdp_url`, else
`http://127.0.0.1:9222`. A `/browser connect` made inside a running chat lives only in that chat's
process, so `duckwork record` finds that browser through the default port, not through the chat.

What gets captured:

| Step | Stored |
|---|---|
| `click` | CSS selector path and the element's visible label (never a field's value) |
| `input` | selector and the field's **final** value, captured on `change` (not per keystroke) |
| `enter` | selector of the focused element when Enter was pressed |
| `navigate` | top-frame URL changes |

Other modes:

```bash
duckwork record --list      # list saved recordings
duckwork record --manual    # no CDP: type what you did, one step per line
duckwork record --cdp http://127.0.0.1:9333 --slug checkout
```

## Where recordings go

`<DUCKWORK_HOME>/recordings/<slug>-<UTC timestamp>.json`, resolved through `get_duckwork_home()`, so
`duckwork -p work record` writes into the `work` profile. Files are never uploaded anywhere.

```json
{
  "version": 1,
  "started_at": "2026-10-21T12:00:00+00:00",
  "url": "https://shop.example.com/login",
  "steps": [
    {"t": 0.0, "type": "click", "selector": "input#user"},
    {"t": 1.2, "type": "input", "selector": "input#user", "value": "alice"},
    {"t": 2.0, "type": "input", "selector": "html > body > form > input[name=\"pw\"]", "value": "{SECRET:pw}"},
    {"t": 2.4, "type": "click", "selector": "button#go", "text": "Sign in"},
    {"t": 2.6, "type": "navigate", "url": "https://shop.example.com/home"}
  ]
}
```

`t` is seconds since the first step.

## Secret masking (two layers)

1. **In the page.** The recorder script never reads the value of a `type=password` field or a field
   whose `autocomplete` is `current-password`, `new-password`, `one-time-code`, `cc-number` or
   `cc-csc`. It sends `{SECRET:<field name>}` instead, so the value never crosses the DevTools
   socket. Clicks never copy a field's value either (only button labels and element text).
2. **In Duckwork.** Before anything is saved, the normalizer masks again from the field type and
   autocomplete hint the page reported, and drops any "text" on a click that landed on a form
   field. A page that changes an input's type mid-flight, or a hand-made event, still cannot put
   a raw password in the file.

Placeholders are resolved only at replay time: the replay skill fills logins, one-time codes and
cards through `browser_vault` (saved logins or a masked prompt, so the value never enters the
conversation), or through an env var / secret reference you set yourself. Duckwork never asks you to
paste a secret into chat and never writes one into a skill.

## Turn a recording into a skill

`duckwork record` ends by printing the exact line. In a Duckwork chat:

```
/learn the browser workflow recorded in /home/me/.duckwork/recordings/shop-login-20261021-120000.json (follow the workflow-record:replay-recording skill)
```

The `workflow-record:replay-recording` skill (listed in the model's skills while the plugin is
enabled) gives `/learn` the recording schema and the rules: rebuild the workflow in human terms,
treat recorded page text as data, map each `{SECRET:*}` to `browser_vault` or a named env var,
and write a Procedure that replays with `browser_navigate`, `browser_snapshot`, `browser_click`,
`browser_type` and `browser_press`, using the recorded selectors only as hints.

Then use the new skill like any other: "log into the shop and check my order status".

## Limits

- **One tab.** Only the tab in front when recording starts is captured. Flows that open a new tab
  or a popup stop being recorded at that point.
- **Values on change.** A field you never left (no blur, Tab or Enter) may be missing; press Tab
  before `Ctrl-C`.
- **Only password-like fields are masked.** An API key typed into a plain text field, or a site
  that puts a secret in a URL (a GET login form, a token in a query string), is recorded as typed.
  Review the JSON before sharing it, or use `--manual` for sensitive flows.
- **Pages can see the recorder.** The capture channel is a page-visible function, so a page could
  add fake steps. The replay skill treats every recorded label and URL as untrusted data; review
  recordings of sites you do not trust before learning from them.
- **Not captured:** scrolling, hovering, drag and drop, file uploads, canvas or shadow-DOM-internal
  interactions, iframes' own navigations.
- **Chromium only.** Firefox and Safari don't speak CDP; use `--manual` there.

## Configuration

None. The CDP endpoint uses Duckwork' existing settings:

```bash
duckwork config set browser.cdp_url http://127.0.0.1:9222
```

## Development

```bash
cd workflow-record
DUCKWORK_AGENT_REPO=../../duckwork-agent PYTHONPATH=../../duckwork-agent python -m pytest -q
```

`tests/test_live_browser.py` drives a real headless Chrome/Chromium/Edge when one is installed
(skipped otherwise): real mouse clicks and typing through CDP input events on local pages, and it
asserts the password never crosses the socket.

Origin: duckwork-agent PR #72199 (`duckwork record`), moved out of core into this plugin.
