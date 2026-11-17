# Anthropic Claude Code "dynamic workflows" — JS grammar fact sheet

Harvested 2026-09-29 from the sources listed at the end. Every statement below is
either a verbatim quote (in quote blocks / code fences) or a paraphrase with a
[S<n>] source tag. Items the sources do NOT document are marked **NOT DOCUMENTED**
rather than inferred.

Version floor: "Dynamic workflows require Claude Code v2.1.154 or later" [S9 changelog;
the rendered doc page S1 does not itself state the number]; the Agent SDK `Workflow`
tool "is available in Agent SDK v0.3.149 and later"
[S3]; the cookbook pins `claude-agent-sdk>=0.2.90` as the Python SDK floor [S4, S5].
Latest changelog entry seen while harvesting: 2.1.284 (September 28, 2026) [S9].

---

## 1. What a workflow script is

> A dynamic workflow is a JavaScript script that orchestrates many subagents at once.
> Claude writes the script for the task you describe, and a runtime executes it in the
> background while your session stays responsive. [S1]

> The body is plain JavaScript with top-level `await`. `agent()` spawns one subagent,
> `pipeline()` runs one per item in a list, and `parallel()` runs a set of agent tasks
> at the same time and waits for all of them. [S1 §"What the saved script looks like"]

> `script` | `string` | Inline workflow script. Must begin with
> `export const meta = { name, description }` as a literal, followed by the script body
> using `agent()`, `parallel()`, `pipeline()`, and `phase()`. An optional `phases` array
> in `meta` groups agents under named stages in the progress view [S3, WorkflowInput table]

Files are `.js`: ".claude/workflows/*.js" and "Each `.js` file is a dynamic workflow"
[S7]; plugin manifest `workflows` field takes "Workflow `.js` files or directories" [S8].

### 1.1 Canonical minimal example (verbatim, S1)

```javascript
export const meta = {
  name: 'audit-routes',
  description: 'Audit every route handler for missing auth checks',
}

const found = await agent('List every .ts file under src/routes/.', {
  schema: { type: 'object', required: ['files'], properties: { files: { type: 'array', items: { type: 'string' } } } },
})

const audits = await pipeline(found.files, file =>
  agent(`Audit ${file} for missing authentication checks.`, { label: file }),
)

return audits.filter(Boolean)
```

Note the script body uses a top-level `return` (also in the cookbook script: `return report`)
[S1, S5].

---

## 2. The `meta` export block

### 2.1 Fields documented

- `name` (string) — required literal. Used as the `/<name>` command; plugin workflows
  become `/<plugin>:<meta.name>` [S1]. Returned as `workflowName` ("The `meta.name` from
  the workflow script") [S3 WorkflowOutput].
- `description` (string) — required literal [S1, S3].
- `phases` (optional array of `{ title: string }`) — "An optional `phases` array in
  `meta` groups agents under named stages in the progress view" [S3]. Cookbook table:
  "`export const meta = {name, description, phases}` | Declares the workflow's name and
  phases; the progress UI groups agents under these phases" [S5].
- `whenToUse` — **NOT DOCUMENTED** in any fetched source (grep of S1, S3, S5, S7, S10
  found no `whenToUse` / `when_to_use` on workflows; `when_to_use` exists only as a
  *skill* frontmatter key [S7 line 1516]).
- `title` / `description` passed as Workflow-tool *inputs* are "Ignored; the script's
  `meta` block sets the title/description" [S3].

### 2.2 The static-read law (verbatim, S1 §"Edit a saved script")

> * **`meta` block**: keep `export const meta` as the first statement, and keep it a
>   plain object literal with a `name` and a `description`. If it contains anything
>   other than literal values, such as a variable, a function call, or a spread, Claude
>   Code drops `/<name>` from `/` autocomplete.
> * **Body**: besides `agent()`, `pipeline()`, and `parallel()`, you can call `phase()`
>   to group the agents that follow under a title in the progress view, call `log()` to
>   show a message above the phases, and read the `args` global. If the body has a
>   syntax error, Claude Code reports it when you run the workflow.
> * **`phases`**: if you list them in `meta`, give each entry exactly the title you pass
>   to `phase()`. A `phase()` title with no entry gets a progress group of its own.
> * **Timestamps and randomness**: Claude Code makes `Date.now()`, `Math.random()`, and
>   a no-argument `new Date()` throw inside the script, so that a relaunched run repeats
>   the same `agent()` calls. Pass a timestamp in through `args` instead.

Changelog corroboration: "Improved startup time in projects with `.claude/workflows/`
scripts: listing them no longer parses each script" [S9] (i.e. meta is read statically).

### 2.3 meta with phases (verbatim, from the Claude-generated cookbook script, S5)

```javascript
export const meta = {
  name: 'orbitcart-fact-check',
  description: 'Fact-check the OrbitCart investor update against source documents',
  phases: [
    { title: 'Extract' },
    { title: 'Verify' },
    { title: 'Skeptic' },
    { title: 'Report' },
  ],
}
```

---

## 3. Runtime globals / primitives

The sources document exactly these callables available to the script body: `agent()`,
`parallel()`, `pipeline()`, `phase()`, `log()`, plus the `args` global [S1, S3, S5].
No formal TypeScript signatures are published in the fetched sources; the shapes below
are what the docs state in prose plus the verbatim call forms observed.

### 3.1 `agent(prompt, options?)`

Cookbook primitive table (verbatim, S5):

> | `agent(prompt, options)` | Spawns one subagent with a **clean context**: it sees only
> the prompt string it's given, nothing else. Options can set a `label`, a `phase`, a
> JSON `schema` for structured output, and a `model` |

Documented options:

| option   | documented meaning | source |
|----------|--------------------|--------|
| `label`  | Per-agent label shown in progress view. Observed: `{ label: file }`, `{ label: 'extract', ... }`, `` { label: `verify-${claim.number}`, ... } `` | S1, S5 |
| `phase`  | Assigns the agent to a named phase. Observed: `{ ..., phase: 'Verify', schema: VERIFY_SCHEMA }` | S5 |
| `schema` | JSON Schema; "If you pass a `schema` on an `agent()` call, that subagent returns JSON matching the shape instead of prose." | S1 |
| `model`  | Per-stage model. "A model the script names for a stage counts as the per-invocation model in that order." (See §7.) | S1, S5 |

Documented `agent()` behaviors:

- Return value: the agent's result (prose string, or parsed JSON when `schema` given).
  "An `agent()` call resolves to `null` if you stop it mid-run or it hits an
  unrecoverable API error." [S1]
- Schema pre-check: "Claude Code checks the schema before starting the subagent: when it
  can prove the schema contradicts itself, the call fails with an error naming the
  contradiction, and the subagent never starts. One contradiction it can prove is a
  `required` key that `additionalProperties: false` rules out." [S1] (added 2.1.260 [S9])
- Schema retry cap: "If the subagent's output still fails validation after five
  attempts, the call fails with an error that includes the last validation failure. To
  change the attempt count, set `MAX_STRUCTURED_OUTPUT_RETRIES`." [S1]; env-vars:
  "Defaults to 5, a first attempt plus four retries" [S10].
- Prompt provenance: "In auto mode, the prompt your script passes to `agent()` doesn't
  count as a request from you when the classifier reviews that subagent's actions,
  because Claude Code marks it as text the script computed." [S1]
- Each agent: "a full Claude Code agent. It starts with a clean context, sees only the
  prompt the script gives it, and works in your session's working directory with the
  tool allowlist you configured." [S5]
- Return-not-write: "Workflow agents hand back what they find as their return value ...
  an agent that tried to write a report-style file such as `SUMMARY.md` was told to
  return the content instead. Real work products ... write to disk normally." [S5]
- Queueing: "queued `agent()` calls wait for a free slot" [S10].

### 3.2 `parallel(tasks)`

- Docs: "`parallel()` runs a set of agent tasks at the same time and waits for all of
  them." [S1]
- Cookbook: "| `parallel([...])` | Runs a batch of agents concurrently and **waits for
  all of them** (a barrier) before continuing |" [S5]
- Limit: "Up to 4,096 items in a single `parallel()` or `pipeline()` call: the runtime
  rejects a longer list with an error" [S1].
- No verbatim `parallel()` call appears in the fetched scripts; argument element type
  (promise vs. thunk) is **NOT DOCUMENTED** beyond `parallel([...])`.

### 3.3 `pipeline(items, stage1, stage2, ...)`

- Docs: "`pipeline()` runs one per item in a list" and "`pipeline()` keeps each `null` in
  the results array, which is why the example ends with `.filter(Boolean)`" [S1].
- Cookbook: "| `pipeline(items, stage1, stage2, ...)` | Runs each item through a sequence
  of stages **independently**, so item A can be in stage 2 while item B is still in
  stage 1 |" [S5]
- Observed stage-function arities (S5 script): stage 1 receives `(claim)`; stage 2
  receives `(verifyResult, claim)` — i.e. previous stage output first, original item
  second. A stage may return a plain `Promise` (`Promise.resolve(...)`) instead of an
  `agent()` call, and may chain `.then()` on `agent()`.
- Result: `await pipeline(...)` resolves to an array aligned to `items` [S1, S5].
- Limit: 4,096 items per call [S1].

Verbatim excerpt (S5) showing the multi-stage form:

```javascript
const results = await pipeline(
  claims,
  (claim) => agent(
    `...`,
    { label: `verify-${claim.number}`, phase: 'Verify', schema: VERIFY_SCHEMA }
  ),
  (verifyResult, claim) => {
    if (!verifyResult || verifyResult.verdict !== 'confirmed') {
      return Promise.resolve(verifyResult ? { ...verifyResult, skeptic_reviewed: false } : null)
    }
    return agent(
      `...`,
      { label: `skeptic-${claim.number}`, phase: 'Skeptic', schema: SKEPTIC_SCHEMA }
    ).then((skepticResult) => { /* ... */ })
  }
)
```

### 3.4 `phase(title)`

- "call `phase()` to group the agents that follow under a title in the progress view"
  [S1]; "| `phase(\"...\")` | Marks which phase the following agents belong to |" [S5].
- Observed: `phase('Extract')`, `phase('Report')` as bare statements (not awaited) [S5].
- Coupling to meta: "if you list them in `meta`, give each entry exactly the title you
  pass to `phase()`. A `phase()` title with no entry gets a progress group of its own."
  [S1]
- An agent may also be placed via the `phase:` option on `agent()` [S5].

### 3.5 `log(message)`

- "call `log()` to show a message above the phases" [S1]. Observed:
  ``log(`Extracted ${claims.length} claims from investor_update.md`)`` [S5].

### 3.6 Script return value

- "| `return {...}` | Whatever the script returns is what comes back to your session |"
  [S5]. Observed `return audits.filter(Boolean)` [S1] and `return report` [S5].

---

## 4. `args` global

> A saved workflow can accept input through the `args` parameter. The script reads it as
> a global named `args`. Use this to supply a research question, a list of target paths,
> or a configuration object at invocation time instead of editing the script for each
> run. [S1]

> Claude passes the list as structured data, so the script can call array and object
> methods on `args` directly without parsing it first. If `args` is omitted, the global
> is `undefined` inside the script. [S1]

Workflow tool input: "`args` | `unknown` | Input value exposed to the script as the
global `args`, for parameterized named workflows such as a research question or a list
of file paths. Pass arrays and objects as actual JSON values, not as a JSON-encoded
string" [S3]; TypeScript type comment: `args?: unknown; // any JSON value; the published
typings render this as an object map` [S3].

Determinism tie-in: timestamps must be passed "in through `args` instead" because
`Date.now()` etc. throw [S1].

---

## 5. File locations & discovery

| Location | Facts | Source |
|----------|-------|--------|
| `.claude/workflows/` (project) | "shared with everyone who clones the repo". Runs as `/<name>`. Monorepo: save goes to "the closest `.claude/workflows/` directory that already exists between your working directory and the repository root, or to the repository root if none exists yet. Project workflows also load from every `.claude/workflows/` along that path, and when more than one defines the same name Claude Code runs the one closest to the working directory." | S1 |
| `~/.claude/workflows/` (personal) | "available in every project, visible only to you. If you set `CLAUDE_CONFIG_DIR`, this location is the `workflows/` directory under that path." | S1 |
| Precedence | "If a project workflow and a personal workflow share a name, the project one runs." | S1, S7 |
| Plugin | "Place the script in a `workflows/` directory at the plugin root, or point to a different location with the `workflows` manifest field." "Plugin workflows are namespaced by the plugin name. A plugin called `acme-tools` containing a script whose `meta.name` is `release-audit` runs as `/acme-tools:release-audit`." | S1 |
| Plugin manifest `workflows` | "`workflows` | Path, or array of paths | Workflow `.js` files or directories. Replaces the default `workflows/` scan". Path-only field: accepts "a directory or a file". Semantics: **Replaces the default** (listing `workflows` stops the default `workflows/` scan; to keep both, list `./workflows/` explicitly). Default layout row: "Workflows | `workflows/` | Workflow `.js` files"; example tree shows `workflows/release-audit.js`. | S8 |
| Per-run script | "Every run writes its script to a file under your session's directory in `~/.claude/projects/`. Claude receives the path when the run starts" | S1 |
| Readability gate | "Claude can start a workflow only from a script file the session is already allowed to read. To run a script kept outside your working directory, add its directory with `/add-dir` or a Read allow rule first." | S1 |
| Symlink checks (2.1.216+) | Project: refuses if `.claude`, `.claude/workflows`, or the target file is a symlink. Personal: refuses only if the target file is a symlink. | S1 |
| SDK `projectConfigRoot` | reads "the project's `.claude/` commands, agents, skills, workflows, routines, and output styles from this directory instead of `cwd`" | S3 |

Bundled: `/deep-research` is the built-in workflow; `/workflow-authoring` is the bundled
skill holding "the script-writing reference Claude works from" (requires v2.1.248+) [S1].
The Workflow tool description was cut to ~1k tokens "with the script-writing reference
moved into a bundled `workflow-authoring` skill" (2.1.248) [S9]. That skill's content is
not published on the web pages fetched here.

---

## 6. Runtime constraints & limits (verbatim table, S1 §"Behavior and limits")

> | Constraint | Why |
> | No mid-run user input | A run pauses on its own only for agent permission prompts and a usage-limit wait. For sign-off between stages, run each stage as its own workflow |
> | No direct filesystem or shell access from the workflow itself | Agents read, write, and run commands. The script coordinates the agents |
> | No module loading: a script that contains `import()` fails before the run starts | The script body is plain JavaScript. Put work that needs a library in an agent's task |
> | Up to 16 concurrent agents by default, fewer when Claude Code has fewer CPUs available, including inside a CPU-limited container. To change the limit, set `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS` to a value from 1 to 256, which requires Claude Code v2.1.269 or later | Bounds local resource use |
> | In a fan-out, agents that share the first agent's prompt-cache prefix start up to 5 seconds after it by default | All but the first read the prefix the first agent cached instead of each processing it uncached |
> | Up to 4,096 items in a single `parallel()` or `pipeline()` call: the runtime rejects a longer list with an error | A silent cap would drop part of the workload without telling the script |
> | 1,000 agents total per run | Prevents runaway loops |

Cookbook restatement: "The runtime keeps up to 16 agents running concurrently (fewer on
machines with limited CPU cores) and caps a run at 1,000 agents; a workflow that plans
more work than the concurrency limit queues it until a slot frees up." [S4, S5]

Env var detail: "`CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS` | How many agents a single
workflow run executes at once, from `1` to `256`. By default, a run executes up to 16
agents at once, fewer when Claude Code has fewer CPUs available; queued `agent()` calls
wait for a free slot. Each running agent's transcript stays in Claude Code's memory, so
higher values raise memory use. Takes plain digits only; out-of-range values and other
spellings keep the default. Requires Claude Code v2.1.269 or later" [S10].
`CLAUDE_CODE_WORKFLOW_PREFIX_STAGGER_MS` default `5000`, `0` disables [S1, S10].

Sandbox: "Fixed workflow scripts being able to use dynamic `import()` to run code outside
the workflow sandbox" (2.1.223) [S9]; "Improved Workflow tool sandbox hardening for
errors thrown by async script hooks" (2.1.284) [S9].

Syntax check: "a script that fails its syntax check returns `status: \"async_launched\"`
with `error` set, and never runs." [S3 WorkflowOutput].

Advisory (not caps): `Large workflow` warning at >25 scheduled agents or >1.5M projected
tokens; `workflowSizeGuideline` values `unrestricted` / `small` (<5) / `medium` (<10) /
`large` (<50); default `medium`, or `small` on Pro with v2.1.271+ [S1].

---

## 7. Plain-JS rule, TypeScript, and loops

- Language: "The body is plain JavaScript with top-level `await`." [S1]; "The script body
  is plain JavaScript." [S1 limits table]; files are `.js` [S1, S7, S8].
- Module loading: "`import()` fails before the run starts" [S1]. Static `import`
  statements are not separately mentioned; the only documented export is
  `export const meta`.
- TypeScript / transpilation: **NOT DOCUMENTED**. No fetched source states whether TS
  syntax is rejected or whether any transpile step exists; the sources only say "plain
  JavaScript" and `.js`.
- Loops / while / retry constructs: the only documented control flow is ordinary JS.
  "| Plain JavaScript between calls | Filtering, deduplication, merging, and loops, all
  exact, instant, and free of token cost |" [S5]; "A workflow script holds the loop, the
  branching, and the intermediate results itself" [S1]. No dedicated `loop()`/`until()`
  primitive appears in any fetched source. Example prompt for loops: "keep fixing the
  reported errors until the type check passes or two rounds in a row make no progress"
  [S1] — expressed as a prompt, not a primitive. Runaway loops are bounded by the
  1,000-agents-per-run cap [S1].
- Determinism: `Date.now()`, `Math.random()`, no-arg `new Date()` throw [S1].

---

## 8. Model routing precedence per stage

> Claude Code picks each workflow agent's model in the same order it uses for subagents.
> A model the script names for a stage counts as the per-invocation model in that order.
> When nothing else assigns one, the agent runs on your session's model. [S1 §Cost]

Subagent order (verbatim, S6 §"Choose a model"):

> 1. The per-invocation `model` parameter
> 2. The subagent definition's `model` frontmatter, where `inherit` selects the main conversation's model
> 3. The `CLAUDE_CODE_SUBAGENT_MODEL` environment variable, when you set it to a model alias or model ID
> 4. The main conversation's model

Applied to workflows: `agent(prompt, { model })` = step 1. Accepted values (per S6):
aliases `sonnet`, `opus`, `haiku`, `fable`; full IDs such as `claude-opus-5-5` /
`claude-sonnet-5`; `inherit`.

- Override-all: `CLAUDE_CODE_SUBAGENT_MODEL` is "The default model for subagents, agent
  team teammates, and workflow agents that aren't assigned a model another way" [S10];
  `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` (v2.1.257+) forces one model onto "subagents,
  teammates, and workflow agents" [S6, S10]. Cookbook: "override every agent at once with
  the `CLAUDE_CODE_SUBAGENT_MODEL` environment variable" [S5].
- Allowlist substitution: "When your organization's `availableModels` allowlist blocks a
  model the script requests for an agent, that agent runs on a substituted model instead
  ... The run's progress view in `/workflows` shows a warning naming both the requested
  and substituted models." [S1]
- Fallback bug fixed 2.1.283: "Fixed dynamic workflows started during a model fallback
  running every agent on the fallback model instead of retrying the configured model" [S9].
- Prompt-cache sharing keys on "the same model, effort level, agent type, tools, output
  schema, and working directory" [S1].

---

## 9. Worktree isolation for workflow subagents

- **NOT DOCUMENTED as an `agent()` option.** The workflows page never mentions
  worktrees; its only related text is an example *prompt*: "use a workflow to migrate
  every component under src/components/ from JavaScript to TypeScript, working on each
  file in its own isolated copy" and the caption "transform each one in an isolated copy
  so edits don't conflict" [S1]. How the generated script achieves that is not shown.
- Subagent-level facts (S6, custom subagent frontmatter, not workflow grammar):
  "`isolation` | No | Set to `worktree` to run the subagent in a temporary git worktree,
  giving it an isolated copy of the repository branched by default from your default
  branch rather than the parent session's `HEAD`. The worktree is automatically cleaned
  up if the subagent makes no changes"; and via Agent tool "it can pass
  `isolation: \"worktree\"`" for forks [S6].
- Default cwd: workflow agents work "in your session's working directory" [S5].
- Background subagents keep the `EnterWorktree` / `ExitWorktree` built-in tools [S6].

---

## 10. Permissions, invocation & resume (grammar-adjacent facts)

- Workflow tool permission rules: "`Workflow` in your allow rules approves every
  workflow, and `Workflow(<name>)` approves one saved workflow by name." [S1]
- SDK: subagents "run in `acceptEdits` mode and inherit that allowlist" [S5]; "In
  `claude -p` and the Agent SDK, Claude Code never shows this prompt." [S1]
- WorkflowInput (verbatim, S3):

```typescript
type WorkflowInput = {
  script?: string;
  name?: string;
  scriptPath?: string;
  args?: unknown; // any JSON value; the published typings render this as an object map
  resumeFromRunId?: string;
  title?: string; // ignored; the script's meta block sets the title
  description?: string; // ignored; the script's meta block sets the description
};
```

  "At least one of `script`, `name`, or `scriptPath` is required." `scriptPath` "Takes
  precedence over `script` and `name`." [S3]

- WorkflowOutput (verbatim, S3):

```typescript
type WorkflowOutput = {
  status: "async_launched" | "remote_launched";
  taskId: string;
  taskType?: "local_workflow" | "remote_agent";
  workflowName?: string;
  runId?: string;
  summary?: string;
  transcriptDir?: string;
  scriptPath?: string;
  sessionUrl?: string; // set when the workflow launched as a cloud session
  warning?: string;
  error?: string;
};
```

- Resume/replay: "Claude Code replays the run in the order agents started"; Completed
  agents return saved results until "The first agent whose prompt differs from the
  previous run"; failed agents "run again, and so does every agent that started after
  it, even ones that completed"; missing journal → `nothing to resume` error [S1].
- Triggers: `ultracode` keyword (human-typed only, v2.1.210+), "use a workflow" phrasing,
  `/effort ultracode`, `claude --effort ultracode` (v2.1.203+) [S1].
- Off switches: `disableWorkflows` setting, `CLAUDE_CODE_DISABLE_WORKFLOWS=1`,
  `/config` toggle [S1, S10].

---

## Sources (all fetched 2026-09-29)

- [S1] https://code.claude.com/docs/en/workflows (rendered, via web_extract) and
  https://code.claude.com/docs/en/workflows.md (raw markdown, via curl — primary text
  quoted above)
- [S2] https://code.claude.com/docs/llms.txt (doc index)
- [S3] https://code.claude.com/docs/en/agent-sdk/typescript.md — `### Workflow` entries
  under Tool input / Tool output schemas (WorkflowInput / WorkflowOutput)
- [S4] https://platform.claude.com/cookbook/claude-agent-sdk-08-dynamic-workflows
- [S5] https://raw.githubusercontent.com/anthropics/claude-cookbooks/main/claude_agent_sdk/08_Dynamic_workflows.ipynb
  (notebook source; the Claude-generated script quoted is cell 15's stored output;
  GitHub page: https://github.com/anthropics/claude-cookbooks/blob/main/claude_agent_sdk/08_Dynamic_workflows.ipynb)
- [S6] https://code.claude.com/docs/en/sub-agents.md — "Choose a model", "Run every
  subagent on one model", `isolation` frontmatter, "Concurrent subagent limit"
- [S7] https://code.claude.com/docs/en/claude-directory.md — `workflows/` entries
- [S8] https://code.claude.com/docs/en/plugins/manifest-reference.md — `workflows` field
- [S9] https://code.claude.com/docs/en/changelog.md — versioned entries cited inline
- [S10] https://code.claude.com/docs/en/env-vars.md — `CLAUDE_CODE_WORKFLOW_*`,
  `CLAUDE_CODE_SUBAGENT_MODEL*`, `MAX_STRUCTURED_OUTPUT_RETRIES`
- Also fetched, no additional grammar facts: https://code.claude.com/docs/en/settings-reference.md,
  https://code.claude.com/docs/en/whats-new/2026-w22.md, https://code.claude.com/docs/en/agents.md,
  https://code.claude.com/docs/en/agent-sdk/python.md
