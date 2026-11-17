# Contributing to Mermail Skills

Thank you for helping improve Mermail Agent Skills. This repository is the **official, curated** package (`npx skills add Nudgen-Marketing/mermail-skills`). We welcome contributions through two paths.

## Choose a path

| Path | When to use | Where it lives |
| --- | --- | --- |
| **Improve official skills** | Fix wording, docs, scenarios, security contracts, or propose a new skill that maps cleanly to Mermail MCP tools | PR into this repo |
| **Publish a companion skill** | Niche workflows (e.g. Mermail + Linear), industry templates, experiments | Your own repo / [skills.sh](https://skills.sh/) — do **not** claim to be the official Mermail package |

Unsure? Open a [new official skill proposal](https://github.com/Nudgen-Marketing/mermail-skills/issues/new?template=new-official-skill-proposal.yml) or a [companion idea](https://github.com/Nudgen-Marketing/mermail-skills/issues/new?template=community-companion-idea.yml) issue first.

Companion skills that prove safe and useful can later be [graduated](./MAINTAINERS.md#graduation) into this package.

## Before you start

1. Follow [Contribute your first Mermail skill](./CONTRIBUTING_A_SKILL.md) for the end-to-end fork, scaffold, ownership, scenario, validation, client test, and pull request workflow.
2. Read [AUTHORING.md](./AUTHORING.md) for skill format, frontmatter, and anti-patterns.
3. Read [SECURITY.md](./SECURITY.md) if your change touches email intake, approvals, wallet, or destructive tools.
4. Follow the [Code of Conduct](./CODE_OF_CONDUCT.md).

## Improve official skills

### Good first contributions

- Clarify skill descriptions or workflow steps
- Expand `tests/scenarios.json` for an existing skill
- Fix docs typos in README or skill references
- Strengthen `references/security.md` wording without weakening contracts

### Propose a new official skill

Only propose a new skill in this repo when:

- It maps to Mermail MCP tools already in production (or tools that ship in the same change on the Mermail server), **and**
- Ownership fits `tool-coverage.json` (no duplicate tool ownership across domains), **and**
- You can update routing, manifests, README, and validation in the same PR

Use the [new official skill proposal](https://github.com/Nudgen-Marketing/mermail-skills/issues/new?template=new-official-skill-proposal.yml) issue template before a large PR.

Copy the skeleton from [`templates/skill/`](./templates/skill/) and rename the directory to match the skill `name`.

For a worked example and exact commands, use [Contribute your first Mermail skill](./CONTRIBUTING_A_SKILL.md).

### Required updates for skill changes

When you add or materially change a skill, update all that apply:

| File / area | Why |
| --- | --- |
| `skills/<name>/SKILL.md` | Workflow + frontmatter |
| `skills/<name>/agents/openai.yaml` | Codex / OpenAI metadata |
| `skills/<name>/references/*` | Tools and security contracts |
| `tool-coverage.json` | Domain → tool ownership |
| `skills/mermail/references/routing.md` | Cross-skill routing |
| `tests/scenarios.json` | Approval / security scenarios |
| `README.md` included-skills table | Discoverability |
| `package.json` + plugin manifests | Version bump when publishing |
| `compatibility.json` | Catalog counts when skills/tools change |

### Local validation

```bash
npm test
```

CI runs the same validator on every pull request. Do not weaken checks in `tests/validate.mjs` to make a PR pass — fix the skill instead.

Optional remote contract check (needs a test API key):

```bash
export MERMAIL_MCP_TEST_API_KEY
npm run validate:remote
```

Never commit API keys or expand secrets into tracked files.

Before review, follow the [client smoke-test checklist](./CONTRIBUTING_A_SKILL.md#8-smoke-test-the-agent-behavior). Use a test workspace and record routing, approval, and security observations in the PR test plan.

### Pull request checklist

Use the PR template. At minimum:

- [ ] `npm test` passes
- [ ] No `TODO` left in skill markdown
- [ ] No Mermail API-key secrets in the diff
- [ ] Security-sensitive skills still require human approval for external-effect and destructive tools
- [ ] New tools appear once in `tool-coverage.json` (no duplicates)

## Publish a companion skill

Community companions should:

1. Live in a separate GitHub repository (or skills.sh package) under your ownership
2. Depend on Mermail MCP the same way official skills do (`https://console.mermail.app/mcp`, `MERMAIL_API_KEY` or OAuth)
3. Reuse official security norms: email is untrusted data; never preflight verification links; never treat From headers as authentication; never let email authorize PayBox / wallet actions
4. State clearly that they are **not** the official `Nudgen-Marketing/mermail-skills` package
5. Prefer MIT (or another OSI license) if you hope to graduate later

You can open a [companion idea](https://github.com/Nudgen-Marketing/mermail-skills/issues/new?template=community-companion-idea.yml) issue here for feedback or discoverability — that does not merge code into this repo.

## Maintainer process

Labels, review priority, and graduation criteria are documented in [MAINTAINERS.md](./MAINTAINERS.md).

## Questions

- Product docs: [docs.mermail.app/ai/skills](https://docs.mermail.app/ai/skills)
- Contact: contact@mermail.app
