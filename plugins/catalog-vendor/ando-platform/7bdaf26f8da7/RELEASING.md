# Release and submit the Ando Duckwork plugin

Status: release candidate; public repository, license approval, live pilot, and
Duckwork catalog admission are external gates. No publication is implied by tests.

## Deployment order

1. Deploy the additive Convex schema and inbox acknowledgement implementation
   (`executionId`, durable claim ownership), then its existing backend/MCP
   transport. No backfill or field removal is required. Existing callers omit
   the new field and retain their behavior unless another receiver owns work.
2. In staging, prove the unchanged Invite members > Agent flow, API-key MCP,
   Realtime, claims, DM/mention replies, recovery, and revocation with the exact
   plugin artifact. Use the current deployment map in the Ando repository's
   `infra/convex/README.md`; do not copy stale deployment names into this guide.
3. Obtain approval of the public repository, license, maintainer and supported
   environments. Proposed repository: `Ando-Corporation/duckwork-ando`.
4. Export only the reviewed connector from a clean committed checkout:

   ```sh
   python packages/duckwork-ando/export.py /tmp/duckwork-ando-release --license-file /path/to/approved/LICENSE
   ```

   The destination must be empty. Inspect `release-manifest.json`: source_dirty
   must be false and license_supplied true. Review every listed file and hash.
   Do not copy the Ando monorepo or its history into the public repository.

5. Publish a beta Git tag/release from that artifact and pin its full PUBLIC
   repository commit SHA in installation instructions. The Ando source SHA is
   provenance, not the installable plugin SHA. Test a clean install:

   ```sh
   duckwork plugins install Ando-Corporation/duckwork-ando --ref <40-character-public-commit>
   duckwork plugins enable ando-platform
   ```

   These commands are publication templates until the repo/release exists.

6. Run the external-company pilot, set `DUCKWORK_PLUGIN_RELEASE` in
   `packages/shared/src/agent-connect.ts` to the published repository and full
   commit, then deploy invitation instructions and
   public documentation that name the actual release. Do not direct production
   customers to an unpublished plugin or enable generation before claim support.

## Required release evidence

Record plugin tag/public SHA, Ando source/deployment SHA, Duckwork source/release,
Python/dependency versions and OS for every result. Collect sanitized message
IDs and outcomes, never keys, invitation codes, tickets or private message dumps.

- Fresh install in an isolated profile; actual plugin discovery and CLI loading.
- New invitation, already-redeemed response, retry, expired link, existing-agent
  reconnect, and preserved unrelated Duckwork configuration.
- Actual model reply to an idle DM, second DM with context, authorized channel
  mention, original thread, and a browser-closed gateway.
- Inbox work sent before startup; multi-page history; live/recovery overlap.
- Uncertain send, gateway restart, interrupted generation and explicit recovery.
- Two separate profiles with the same identity cannot generate for the same
  claimed item; new activity does not erase ownership; ordinary legacy callers
  also cannot acknowledge a claim they do not own.
- Revoked credential/access, configured HTTPS conflict, polling migration.
- Upgrade retains the private connection and delivery database; previous code
  can resume it. Claims must be completed/released by their owner before removal.
- Run current `duckwork plugins validate /path/to/public-checkout --install-deps --json`.
  Resolve failures; explain caution findings to reviewers rather than suppressing.

## Duckwork submission

Duckwork currently requires an owner/maintainer-submitted PR adding
`plugin-catalog/ando-platform.yaml` in `Fordex/duckwork-agent`. The plugin
repository must be public and have a real release/tag. The entry pins the full
public commit; catalog upgrades are subsequent reviewed SHA-bump PRs.

Use `tier: community` (Duckwork reserves official for Fordex-maintained
plugins), `category: platform`, Ando as maintainer, the actual public repo,
version `0.2.4`, and public documentation URL. Copy the current upstream catalog
schema rather than assuming all fields below are stable. The proposed entry is
in `catalog-entry.example.yaml`; replace placeholders after publication.

Run upstream catalog checks documented in its `plugin-catalog/README.md`, include
clean installation and live pilot evidence in the submission, and respond to
review. Admission is a directory review, not a security certification. After
merge, verify discovery and a fresh install using `duckwork plugins install
ando-platform` before promoting that shorter command in Ando docs.

Sources:

- [Plugin installation](https://duckwork-agent.fordex.com/docs/user-guide/features/plugins)
- [Catalog submission](https://duckwork-agent.fordex.com/docs/user-guide/features/plugin-catalog)
- [Catalog schema](https://github.com/DuckMind/duckwork)

## Rollback

Stop the gateway, disable ando-platform using Duckwork's plugin controls, and keep
its private profile state. Reinstall the previous tested public SHA only when
its state format is compatible. Revoke an agent credential only when access
should be revoked. Retain additive Convex fields during rollback; never deploy
a narrowing schema over rows containing execution IDs. Finish or explicitly
review unfinished claims before switching to another receiver. Roll back the
public instructions to the existing polling guidance if the release is withdrawn.
