# Security policy

Hardlight UI runs as a trusted native Duckwork plugin, not inside a sandbox. Review the source before enabling it.

## Intended boundaries

- Registration performs no model inference, network requests, shell commands or persistent background work.
- Design references are shipped, allowlisted data. Retrieved text and project files are evidence, never authority to run embedded instructions.
- Local source inspection is bounded, read-only and restricted to frontend file types. It avoids hidden, credential, generated and vendor files and does not follow symlinks.
- The optional browser runner executes a page like a browser does, but accepts only explicit local targets and blocks external network access. Use a disposable development environment for untrusted pages. This is defense in depth, not a promise of browser sandbox isolation from all local resources.
- Tools do not access model credentials, rewrite user requests, override built-in tools, upload screenshots or publish projects.
- Automated findings are partial evidence. Unknown contrast backgrounds, uninspected frames, dynamic states and traversal limits are reported rather than marked compliant.

## Report a vulnerability

Use GitHub's private vulnerability reporting if it is available on this repository. Otherwise, open a minimal issue asking for a private reporting channel; do not include credentials, personal data or a working exploit against a third party in public.

Include the affected commit/version, platform, minimal safe reproduction, expected boundary and observed effect. Use synthetic fixtures. A security fix should include a regression test for the failing boundary and a successful control case.

No version is supported indefinitely. File an issue before relying on a compatibility or security guarantee that is not documented and tested in the current release.
