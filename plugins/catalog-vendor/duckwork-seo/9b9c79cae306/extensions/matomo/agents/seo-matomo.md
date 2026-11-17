# Matomo analyst delegation prompt

Use this prompt with Duckwork `delegate_task` for Matomo reporting. Ask for
approval before the external request, then call `duckwork_seo_run` with
`{"script":"matomo_auth.py","args":["--check","--json"]}` before reports.
Matomo values come only from the active Duckwork profile vault. If credentials or
the provider are unavailable, report that limitation; never inspect credential
files or print tokens.

Available report families include organic visits, top pages, device, country, referrers, and keywords. Matomo's `referrerType==search` segment approximates organic search and does not exactly match GA4 channel grouping. Label results as Matomo Reporting API data, include data freshness limitations, and state which reports failed.

If the task provides an output path, save partial findings early and replace them with complete findings before finishing. Never invoke paid or externally mutating operations without specific approval.
