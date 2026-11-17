---
name: showly-reports
description: Create or edit a visual HTML report, explainer, comparison, or diagram page from an answer, research, or notes using Showly's bundled renderer. Use when a visual report is requested or materially helps explain a complex topic. For existing site management use showly-hosting; respect requests for plain text and existing website frameworks.
---

# Showly reports

Write an extended Markdown draft; the bundled renderer handles layout, diagrams,
themes and light/dark mode. This capability produces local static HTML. Upload
only when the user requests sharing or hosting. Do not enable an always-on rule
or change the user's global agent configuration.

## Generate a report

Requires a local shell and Node.js 20+. If these are unavailable, explain that
this bundled renderer needs a local runtime; connecting the remote Showly MCP
alone does not provide rendering. Do not claim a report was generated.

Resolve `scripts/report.mjs` relative to this SKILL.md and invoke its absolute
path with Node. Use this Showly entrypoint rather than a globally installed `am`
or the vendor file. No dependency installation is needed. The renderer is pinned
and updates with Showly; it does not check upstream for updates or open browsers.

1. Write a draft in the user's language. Use sections for the explanation's
   natural parts and select components using [the format guide](references/format.md).
   Keep source evidence and links in the report. Do not invent facts or numbers.
2. Save the draft outside a dedicated upload directory, then render:

   ```sh
   node /absolute/path/to/showly-reports/scripts/report.mjs render answer.md -o report-site/index.html
   ```

   `-` reads the draft from stdin. Supported flags include `--theme
auto|blueprint|shadcn|paper`, `--template sheet|doc`, `--mode auto|light|dark`
   and `--style off|80|strict`. The output path is required. Use a separate
   directory per report so unrelated files cannot be uploaded accidentally.

3. Read errors, correct the named draft component, and render again. The default
   writing check warns; strict mode refuses invalid prose. Limit automatic
   correction to two rounds, then report the remaining problem honestly.
4. Inspect the rendered page with an available browser, including a narrow
   viewport for wide diagrams or tables. If browser inspection is unavailable,
   distinguish successful rendering from visual verification.
5. If the user requested an online preview or shareable link, continue below
   automatically and return the hosted result. Otherwise return a clickable local
   artifact link and briefly offer to host the report on Showly; wait for that
   request before uploading.

The page embeds its Markdown source in `#am-source` and offers a Copy source
button. Everything in that source is visible to anyone with page access: include
only the intended report content, never private drafting notes or credentials.
Raw HTML/SVG blocks are rendered as markup; do not run untrusted report HTML in
the Showly control-plane origin.

## Edit an existing report

Keep the original draft and regenerate after broad changes. For a section edit:

```sh
node /absolute/path/to/showly-reports/scripts/report.mjs patch report-site/index.html --panel "Trade-offs" --from revised-panel.md
```

This replaces one section and preserves the other sections. The HTML must have
its embedded source; if it is missing, recover the original draft instead of
inventing it. Upload an edited hosted report to its existing site, not a new site.

## Share through Showly

When sharing is requested, read the co-installed
[showly-hosting skill](../showly-hosting/SKILL.md) for access, authorization,
publishing and result-handling rules. The following steps transport the generated
file without making the model repeat its HTML:

1. For a new report, reuse the known project or call `list_projects`. For an
   existing report, reuse its saved `siteId` and inspect `get_site_context`.
2. Pack only the report directory, with `index.html` at the archive root:

   ```sh
   tar -cf report-source.tar -C report-site index.html
   ```

   If the report references local assets, include those assets with their
   relative paths. Keep the tar and draft outside the upload directory.

3. Call `request_upload_url`. PUT the tar bytes to its returned `uploadUrl`
   using its `contentType` (`application/x-tar`). Use a shell or file-transfer
   tool; do not paste the generated HTML into model tool arguments. Check the
   HTTP result before creating a version. Do not print or retain signed URLs.
4. For a new site, call `create_site_from_html` with `projectId`, `name`,
   `siteSlug` and the returned `sourceBundleId`. For an update, call
   `create_preview` with the existing `siteId` and `sourceBundleId`. Do not send
   `files` or `changesetId` alongside the bundle ID.
5. Retain any returned one-time password and poll `get_preview_status` for the
   returned deployment until ready or failed. On failure, inspect the deployment
   diagnostics and report the cause; do not create sites repeatedly. Return the
   actual ready URL, its access and unpublished state, and the management URL.
6. Save the returned `siteId` and deployment ID in a local sidecar outside the
   upload directory for subsequent edits. Store no tokens, passwords or signed
   URLs there. Formal publishing follows showly-hosting's confirmation flow.

If Showly authorization is missing, keep the local report and follow the hosting
skill's sign-in instructions. Do not silently fall back to an expiring anonymous
trial. A user who explicitly wants the no-account route can use
<https://showly.ai/drop>; browser verification may be required.

## Scope and provenance

This entrypoint supports static reports, built-in themes, diagrams and section
patching. Video, voice synthesis, MP4 export and upstream config/cleanup commands
are outside this integration. See [upstream provenance](references/upstream.md)
and [third-party licenses](THIRD_PARTY_LICENSES.txt).
