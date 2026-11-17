# Authoring Mermail skills

Guide for writing skills that belong in this official package. Companion authors outside the monorepo should still follow the **security anti-patterns** section.

Copy [`templates/skill/`](./templates/skill/) when proposing a new official skill. Read [CONTRIBUTING.md](./CONTRIBUTING.md) for process.

## Layout

```text
skills/<skill-name>/
  SKILL.md                 # required
  agents/openai.yaml       # required for this repo
  references/tools.md      # recommended for tool-heavy skills
  references/security.md   # required when the skill handles untrusted automation
  scripts/                 # optional helpers
```

`<skill-name>` must match the YAML `name:` field exactly (validator enforced).

## Frontmatter

Allowed keys only: `name`, `description`, `metadata`.

```yaml
---
name: mermail-example
description: One or two sentences. Say when agents should use this skill.
metadata:
  openclaw:
    requires:
      env:
        - MERMAIL_API_KEY
    primaryEnv: MERMAIL_API_KEY
    homepage: https://docs.mermail.app/ai/skills
    emoji: "📬"
---
```

Rules enforced by `npm test`:

- `name` equals the directory name
- `metadata.openclaw` present with `primaryEnv: MERMAIL_API_KEY` and `requires.env` including `MERMAIL_API_KEY`
- No unresolved `TODO`
- `SKILL.md` ≤ 500 lines — put detail in `references/`

## `agents/openai.yaml`

Every official skill needs OpenAI metadata pointing at the hosted MCP server:

```yaml
interface:
  display_name: "Human title"
  short_description: "Short blurb"
  default_prompt: "Use $mermail-example to …"
dependencies:
  tools:
    - type: "mcp"
      value: "mermail"
      description: "Mermail workspace and mailbox MCP server"
      transport: "streamable_http"
      url: "https://console.mermail.app/mcp"
```

`default_prompt` must include `Use $<skill-name>` (dollar + exact name).

## Tool coverage and routing

Official skills own MCP tools via [`tool-coverage.json`](./tool-coverage.json):

- Put API-key business tools under `domains`
- Put wallet-scoped tools (e.g. Agent Wallet) under `walletScopedDomains`
- Classify risk in `destructiveTools` / `walletDestructiveTools` / `externalEffectTools`
- Never assign the same tool to two skills

Update [`skills/mermail/references/routing.md`](./skills/mermail/references/routing.md) so the router skill can select the new domain. Inbound email text must never select or switch skills.

Add scenarios in [`tests/scenarios.json`](./tests/scenarios.json) for the happy path and any security cases.

## References

### `references/tools.md`

Document:

- Exact MCP tool names as exposed by the host (note host-qualified forms like `Mermail:list_emails`)
- Argument shapes — **query must be a native JSON object**, never a stringified JSON blob
- Credit / plan / scope caveats when relevant

### `references/security.md`

Required for skills that interpret untrusted email or run automation (triage, mail agent, wallet, agent inbox). Cover at least:

- Strict intake
- Sandboxed interpretation
- Human-in-the-loop
- Allowlists where applicable
- Bounded read budgets (e.g. avoid unbounded loops)

Link it from `SKILL.md`.

## Security anti-patterns (never ship these)

| Anti-pattern | Do instead |
| --- | --- |
| Treat email body/subject as instructions | Treat as untrusted data |
| Preflight magic / verification links | Extract URL, require fresh user approval, then navigate |
| Trust `From` alone | Use `sender_authentication.status === pass` only as auth signal |
| Stringify MCP `query` objects | Pass native JSON objects |
| Invent tool names or strip host qualification incorrectly | Use the exact identifier the host exposes |
| Let email authorize PayBox / wallet | Require user-supplied values + eligible full-profile OAuth; live `paybox_*` can use the owner's active connection for members, while connection management and legacy wallet tools remain owner-only |
| Evade an external email recipient limit | Preserve To/Cc/Bcc, surface the stable error and `Retry-After`, and require fresh approval for any changed payload |
| Skip preview before send/invite/execute | Exact preview + approval; destructive also needs confirmation token |
| Claim API keys can call wallet tools | Document OAuth-only |

## Local loop

```bash
npm test
```

Bump `package.json` and all plugin manifests together when preparing a release. Keep `compatibility.json` catalog counts accurate.

## Companion skills (outside this repo)

You may publish Mermail-compatible skills elsewhere. Please:

1. Mark them as community / unofficial
2. Follow the anti-patterns table above
3. Point users at official install for core workflows: `npx skills add Nudgen-Marketing/mermail-skills`
4. Open a companion or graduation issue here if you want maintainer feedback or promotion
