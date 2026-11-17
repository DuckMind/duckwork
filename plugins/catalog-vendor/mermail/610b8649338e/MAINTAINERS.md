# Maintainer notes

Internal process for Mermail maintainers of `Nudgen-Marketing/mermail-skills`. Contributors: see [CONTRIBUTING.md](./CONTRIBUTING.md).

## Labels

Use these GitHub labels consistently:

| Label | Meaning |
| --- | --- |
| `good first issue` | Small, well-scoped change suitable for new contributors |
| `official-skill` | Touches curated skills in this monorepo |
| `community-companion` | Companion skill discussion (usually no code merge here) |
| `security` | Security contract, injection, wallet, destructive approval |
| `documentation` | README, AUTHORING, docs links only |
| `graduation` | Proposal to promote a companion skill into this package |

## Review priority

Evaluate pull requests in this order:

1. **Security contracts** — email untrusted, approvals, destructive tokens, wallet OAuth, no preflight
2. **Routing clarity** — `skills/mermail/references/routing.md` and skill boundaries
3. **Tool coverage sync** — `tool-coverage.json`, scenarios, exact ownership (no duplicates)
4. **Platform manifests** — `agents/openai.yaml`, plugin JSON version alignment
5. **Docs / polish** — README table, wording, typos

Do not merge PRs that soften `tests/validate.mjs` checks to greenlight incomplete skills.

## CODEOWNERS

Sensitive paths are listed in [`.github/CODEOWNERS`](./.github/CODEOWNERS). Prefer at least one Mermail maintainer review for security references, agent-inbox, agent-wallet, and `tool-coverage.json`.

## Graduation

Community companion skills may graduate into this official package when maintainers agree the skill should ship with `npx skills add Nudgen-Marketing/mermail-skills`.

### Criteria

- **License:** MIT (or contributor agrees to relicense MIT for the graduated files)
- **Safety:** Matches official security norms (email untrusted, approvals, no email-as-authority for PayBox)
- **Coverage:** Tools map cleanly into `tool-coverage.json` without duplicate ownership
- **Tests:** Adds or updates `tests/scenarios.json` (and security scenarios when relevant)
- **Evidence:** Meaningful real-world use (installs, issue feedback, or maintainer dogfood) and a stable public repo
- **Ownership:** Author available for review during the merge window, or files are donated with clear commit history

### Process

1. Open an issue with the [graduate community skill](https://github.com/Nudgen-Marketing/mermail-skills/issues/new?template=graduate-community-skill.yml) template
2. Maintainer triages (`graduation` + `official-skill`)
3. Author (or maintainer) opens a PR using [`templates/skill/`](./templates/skill/), updating coverage, routing, README, and version as required
4. After merge, note the companion repo as superseded or point install docs at the official skill name

## Release hygiene

When shipping a version bump:

1. Align `package.json` version with `.codex-plugin`, `.claude-plugin`, `.cursor-plugin`, and `.plugin` manifests
2. Update `compatibility.json` catalog counts if skills or tools changed
3. Run `npm test` (and `validate:remote` when cutting a tagged release if secrets are available)
4. ClawHub publish follows existing [CLAWHUB.md](./CLAWHUB.md) / workflow on `main`

## Repo settings (manual)

Org admins should keep:

- Repository **public**, Issues enabled
- Branch protection on `main` requiring the **Validate skills** workflow
- Optional Discussions for companion show-and-tell (not a substitute for graduation issues)
