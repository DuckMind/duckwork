# Skill provenance

The source is [`tavily-ai/skills` at `778122e`](https://github.com/tavily-ai/skills/tree/778122e5f9c680f541eeceda5a5b36405eb7980c/skills).
The full source commit is `778122e5f9c680f541eeceda5a5b36405eb7980c`.
Tavily's MIT license and source attribution are retained. Skill frontmatter
credits the Duckwork adaptation separately from Tavily's original material.

## Included skills

- `tavily-search`
- `tavily-extract`
- `tavily-map`
- `tavily-crawl`
- `tavily-research`
- `tavily-best-practices`

This is the user-selected MCP bundle. `tavily-cli` and
`tavily-dynamic-search` are excluded because their setup and disk-filtering
workflows depend on the Tavily CLI. No use-case skills are bundled.

## MCP adaptations

The operational skills preserve their source tasks: discover sources, extract
selected pages, map before broad collection, bound crawls, and reserve Research
for multi-source synthesis. Source selection, evidence verification, extraction
failure checks, and research model selection are retained.

CLI invocations are replaced with examples for Duckwork's
`mcp__tavily__tavily_*` tools. Command flags become MCP arguments where the
advertised schema supports them: for example, `--depth` becomes
`search_depth`, hyphenated names become underscored argument names, domain/path
lists become JSON arrays, and external-link selection becomes a boolean.
The current hosted schemas were read on 2026-10-21; the examples are checked
against that interface in the package tests.

The source CLI's installation, keyless login, automatic skill refresh, output
files, and separate Research polling commands are not presented as MCP
features. OAuth and API-key instructions use Duckwork's profile-aware connection
configuration. No Tavily CLI process or separate CLI authentication is required.
Only inputs in the live MCP schema are documented as operational controls.

Descriptions are shortened to at most 60 characters and end with a period.
Content follows Duckwork's required section order. Qualified skill names are
discovered using `skills_list`; `skill_view` loads skills and references.
Rate/credit errors stop the workflow; failed attempts count against the user's
request budget. These are agent instructions rather than runtime quota guards.

## Best Practices references

`tavily-best-practices` adapts the source's retrieval planning, query design,
source filtering, relevance checks, Map-before-Crawl guidance, Research model
selection, and evidence verification to the same MCP connection as the other
bundled skills. All examples use advertised MCP arguments.

The Search, Extract, Map/Crawl, and Research guides are rewritten for MCP.
The source's `sdk.md` and `integrations.md` are replaced by `mcp.md` and
`workflows.md`, documenting Duckwork-managed authentication, live tool schemas,
bounded retrieval composition, and failure handling. Direct API/SDK examples,
client installation, external framework setup, and separate polling flows are
outside the selected MCP-only bundle. These guides are adaptations, not
byte-identical copies or a claim of full direct API capability coverage.

No skill installs or invokes the Tavily CLI or an SDK. There are no credential
assignments or token-store readers in the bundle. The plugin has no executable
runtime or skill scripts; Duckwork manages tool execution and approvals.
