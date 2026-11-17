# Unlighthouse setup

Unlighthouse is a local multi-page Lighthouse runner retained as optional extension material. It does not require a provider API key, but needs Node.js/npm and package/browser dependencies. The former installer that copied a skill into Claude Code is not a supported setup flow in this fork.

Check the bundled runner's options and execute it through Duckwork' managed runtime when it is allowlisted:

```bash
duckwork seo run unlighthouse_run.py --help
```

Unlighthouse performs lab measurements by crawling the target site; keep route limits appropriate and obtain approval before running a broad crawl. No provider or browser compatibility has been verified by this setup note.
