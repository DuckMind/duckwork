## Summary

<!-- What changed and why -->

<!-- New contributors: follow CONTRIBUTING_A_SKILL.md before completing this checklist. -->

## Path

- [ ] Official skill / docs / validator change in this repo
- [ ] N/A (chore only)

## Checklist

- [ ] `npm test` passes locally
- [ ] No unresolved `TODO` in skill markdown
- [ ] No API keys or Mermail workspace key secrets in the diff
- [ ] If skill wording changed: security / approval contracts are preserved or strengthened
- [ ] If tools/skills added: `tool-coverage.json`, routing, scenarios, and README table updated
- [ ] If version bump: plugin manifests match `package.json`

## Tool ownership and risk

<!-- For tool/skill changes, name the canonical owner and explain external-effect/destructive classification. Use n/a for docs-only changes. -->

## Client smoke test

<!-- List prompts used to verify positive routing, neighboring-skill routing, approval behavior, and untrusted-content handling. Use n/a with a reason when local client testing does not apply. -->

## Skill name(s)

<!-- e.g. mermail-compose-email, or n/a -->

## Test plan

- [ ] Described how you validated the change (validator, manual client check, etc.)
