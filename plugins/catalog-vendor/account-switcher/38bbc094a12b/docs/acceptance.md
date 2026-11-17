# Acceptance ledger — Duckwork Account Switcher

What "accepted" means for this plugin, split into five kinds of evidence. Passing one never
substitutes for another. Nothing below is marked passed unless it ran, and every live result
names its receipt.

Release: **1.2.3**. Last updated 2026-10-17.

1.2.3 adds support for Duckwork 0.22 (the gateway restarts alone; Duckwork Desktop stays open). Proven
on the owner's PC with one real switch before release: `receipts/2026-10-17-unified-runtime-owner-pc.json`.
The live run on the 1.2.3 archive itself is recorded with the release.

1.2.2 answers the catalog review (see [release-notes.md](release-notes.md)): the in-process hold
on Duckwork Desktop's requests is gone and the idle refusal rests on Duckwork's own idle proof; the
dashboard modules are imported as a package; the Claude CLI token renewal is documented; a
wrong-account Claude sign-in is deleted. 1.2.1 changed only the Desktop button. The way a switch
is applied is unchanged since 1.2.0 (rc.4), so the live results below stand for it; rows the
1.2.2 change touches say so. The gates and the live run on the 1.2.2 archive itself are recorded
with the release, outside the archive: an archive cannot contain its own hash.

## A. Automated tests

Run from this repository; no Duckwork needed.

| Item | Status |
|---|---|
| Backend suites (fixture logins, temporary homes, stand-in commands) | **280 passing** |
| Interface suite (stand-in for Duckwork's plugin kit, not the real app) | **34 passing** |
| Real-host import check: `plugin_api.py` loaded the way Duckwork's web server loads it, in Duckwork's own Python with the live checkout importable | **Passed 2026-10-07** on the owner's PC (Duckwork `90d5048f`): 6 routes mounted, no generic sibling name and no `dashboard/` entry in that interpreter, every required public interface present, Duckwork's idle proof readable, no private Desktop server name referenced. |

These prove the logic. They do not prove a switch on a real machine; section D does.

## B. Official validation of the release archive

| Item | Status |
|---|---|
| `duckwork plugins validate --json` on the extracted archive | **Passed on the rc.4 archive**, run by a stock Duckwork (upstream `7154128f`) on the test machine: exit 0, `ok: true`, security scan safe, Desktop surface inside the plugin kit. One documented skipped probe: the plugin has no `__init__.py`, so Duckwork skips its Python capability probe. |
| Duckwork's own installer route (`duckwork plugins install`) from the exact archive, byte for byte | **Passed on 1.2.0 from the public repository** (`duckwork plugins install SmelterLabs/duckwork-account-switcher`, tag `v1.2.0`, stock Duckwork `3cf2eb1c`): 67 of 67 files identical to the release archive, validator ok, enabled. Not repeated for 1.2.2 (the test machine is gone); the public tree is byte for byte the 1.2.2 archive. | `receipts/2026-09-30-duckwork-plugins-install.json` |
| The 1.2.2 archive installed with the plugin's own installer on the owner's PC, then one real switch | **Passed 2026-10-08** (Duckwork `8447d38e`): 15 files, a Claude reapply verified in 73 s, new Desktop and gateway processes, the reopened backend answering with Duckwork's idle proof. | `receipts/2026-10-08-install-1.2.2-owner-pc.json` |

## C. Installer lifecycle

| Item | Status |
|---|---|
| Install, reinstall, roll back, uninstall in a scratch home with stand-in data | Passed on the rc.1 archive; covered by 19 automated tests on the current code. |
| Install and update on a real stock Duckwork, from the rc.4 archive | **Passed**, first profile and a second profile; each profile's own files (`config.yaml`, `.env`, `SOUL.md`, the login store) were byte for byte unchanged. |
| Roll back, and roll back again, on a real stock Duckwork | **Passed**; the second roll back returned the exact bytes of the update. |
| Uninstall on a real stock Duckwork | **Passed**: the 13 installed files removed, a file the user had added kept, the rollback copy kept. |
| Install over a folder the installer does not own | **Refused**, files kept. |
| The installer never enables or disables anything | **Passed**: the plugin stayed enabled through update, roll back and uninstall. |
| The guided settings setup on a real stock Duckwork | **Passed**: as a first run it produced the same folders, account keys and emails as settings written by hand. |

## D. Real switching

Test machine: a clean Windows 11 Pro (25H2, build 26200) virtual machine; Duckwork installed by a
normal signed-in user; real accounts signed in there by their owner. Nothing was copied from
another machine. Most rows ran on Duckwork installed with the install script; the first-time install
and every Claude row ran on a second, blank machine where Duckwork was installed with the official
Windows installer.

| Item | Status | Receipt |
|---|---|---|
| Real Codex switches through the plugin's backend, both directions | **Passed** | `receipts/2026-09-28-vm-real-switch.json` |
| Real Codex switch entirely through the Desktop button and dialog | **Passed**, and again on the rc.4 archive after the Duckwork update (40.1 s, billing confirmed on the wire) | same |
| Duckwork's own gateway stopped and started by the switch (no Windows service) | **Passed** | `receipts/2026-09-28-vm-stock-gateway-lifecycle.json` |
| Which account pays for a request, before and after a switch, measured on the wire | **Passed** | `receipts/2026-09-28-vm-billing-proof.json` |
| Refusal: a login for an account that is not in the settings | **Passed**, nothing changed | `receipts/2026-09-28-vm-refusals-and-failures.json` |
| Refusal: the provider rejects the target login | **Passed**, nothing changed | same |
| Refusal: a conversation is running (dialog, and a forced request) | **Passed on 1.2.0** with the former in-process hold, nothing changed, the conversation kept running. On 1.2.2 the refusal is Duckwork's own idle proof: **automated tests** cover every answer it can give. **Seen live on 1.2.2** (owner's PC): the idle proof read "busy" in the first seconds after Desktop reopened and "idle" in 50 of 50 samples afterwards; a forced refusal with a running conversation was **not run** on 1.2.2. | same, and `receipts/2026-10-08-install-1.2.2-owner-pc.json` |
| An expired login | **Refused while expired.** Duckwork renewed the login by itself within seconds and the switch was then allowed. Not a standing refusal. | same |
| The selected login is dead: warning, and the account that really pays | **Passed** | same |
| Failure while Duckwork is closed: settings changed | **Passed**: previous order restored, Duckwork reopened | same |
| Failure while Duckwork is closed: login store cannot be written | **Passed**: Duckwork reopened, receipt says the restore could not be written | same |
| The switch is cut off while Duckwork is closed | **Failed on rc.3** (a permanent "already in progress"). **Passed on rc.4.** | same |
| A second profile without logins of its own follows the switch | **Passed** | same |
| A profile that holds its own Codex logins | **Not run** on stock Duckwork (automated tests only). | |
| A switch cut off while the choice is being written, with more than one store | **Not run.** | |
| Real Claude switches through the plugin's backend: none selected to one account, then to the other | **Passed** (62.7 s and 67.6 s) | `receipts/2026-09-29-vm-claude.json` |
| Which Claude account a real request uses, before and after a switch | **Passed**: every `claude` process the request started was handed the selected account's login folder, and Anthropic confirmed that folder's owner | same |
| Codex and Claude changed together in one switch, entirely through the Desktop dialog | **Passed** (46.3 s); both proofs repeated afterwards | same |
| A Claude sign-in made as the wrong account | **Refused**: the browser was signed in as another account, and the plugin would not accept the login for the account it was meant for | same |
| Claude sign-in by pasting the code into `setup.cmd claude` | **Not run.** The sign-ins for the test were answered through the browser instead. The same code path is what the internal tool has used. | |
| A first-time install on a blank Windows 11, with no Python on it: Duckwork's official installer, `setup.cmd`, `duckwork plugins enable`, the switch on the plugin's card, then a switch through the dialog | **Passed** (first switch 54.6 s, billing confirmed on the wire) | `receipts/2026-09-29-vm-first-install.json` |
| Duckwork installed with the official Windows installer (`Duckwork-Setup.exe`) | **Passed.** It builds the same install as the install script. | same |
| Duckwork as a Windows Store style package, which Duckwork's source can build but its site does not offer | **Not run.** | |
| The author's own customized Duckwork build with a Windows service gateway | **Passed on 1.2.2** (2026-10-08, Duckwork `8447d38e` with the owner's overlay, gateway as the service `DuckworkGateway`): install, Desktop relaunch, one real switch verified. | `receipts/2026-10-08-install-1.2.2-owner-pc.json` |

## E. Duckwork update

| Item | Status | Receipt |
|---|---|---|
| Update Duckwork from one build to a newer one with Duckwork's own command; plugin, settings and logins survive; preflight, a real switch and the billing proof pass on the new build | **Passed** (upstream `9a0a1625` to `7154128f`, 629 commits) | `receipts/2026-09-28-vm-duckwork-update.json` |
| An update made with Duckwork Desktop's in-app updater | **Not run.** | |
| A Duckwork build that changes an interface the plugin depends on is refused before anything is changed | Automated tests only. | |

## What is still open

1. The listing in the official catalog.

## Release claim rule

The release is complete only when every line that applies to the declared scope is passed with a
receipt. Receipts for the final archive are produced outside it: an archive cannot contain its
own hash.
