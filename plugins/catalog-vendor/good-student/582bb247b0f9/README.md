# duckwork-plugin-good-student

[English](#english) | [中文](#中文)

<a name="english"></a>
## English

**Good-student** is a wrong-question diagnosis and study-action plugin for Duckwork Agent,
built for parents and students: upload wrong-question materials, confirm AI-recognized
candidates, analyze weak knowledge points, generate study plans, and run reassessments.

Design principle: **the host model understands; Good-student is the trustworthy core.**
Recognition output is *candidates only* — nothing enters the child's learning profile until
a parent explicitly confirms it. All data lives in a local SQLite database on your machine;
nothing is uploaded, no API keys required.

### What it provides

- An MCP server (`gs`) exposing 15 `good_student_*` tools (profiles, scores, candidate
  confirmation, analysis, plans, reassessments, weekly brief, export, doctor).
- A bundled `good-student` skill that walks the agent through the
  recognize → confirm → analyze → plan → reassess loop with parent-confirmation gates.
- Data directory defaults to the plugin's own `PLUGIN_DATA` space (`GOOD_STUDENT_DATA`).

### Install

```bash
duckwork plugins install harrylabsj/duckwork-plugin-good-student
duckwork plugins enable good-student
```

Requirements: Python ≥ 3.10 and [uv](https://docs.astral.sh/uv/) (`uvx`) on PATH — the MCP
server is launched via `uvx --from git+https://github.com/harrylabsj/good-student@v0.1.1[mcp]`,
pinned to the exact tag. First launch resolves and caches the environment automatically.

The upstream repo's `docs/privacy/minor-data-protection.md` documents the minor-data
handling rules (local storage, no cloud, parent-consent gating).

### Why the server key is `gs`

The full wire name is
`mcp__agent-plugin-good-student-<hash>__gs__good_student_record_reassessment`-shaped.
Duckwork clamps long MCP tool names to the 64-character provider limit with a hash suffix,
but a short server key keeps more names human-readable. `gs` is the same convention the
official `snyk` (`sn`) and `kiwi` (`kb`) entries use.

<a name="中文"></a>
## 中文

**Good-student（错题教练）**是面向家长和学生的错题诊断与学习行动插件：上传错题材料 →
AI 识别为候选 → 家长确认 → 薄弱点分析 → 学习计划 → 复测闭环。

设计原则：**宿主模型负责理解，Good-student 负责可信。** 识别结果只是“候选”，未经家长
确认绝不写入学习画像。全部数据保存在本机 SQLite（`PLUGIN_DATA` 目录），不上传、无需
API Key。

- MCP server（`gs`）暴露 15 个 `good_student_*` 工具（档案/成绩/候选确认/分析/计划/复测/周报/导出/体检）。
- 捆绑 `good-student` 技能，引导智能体按“识别 → 确认 → 分析 → 计划 → 复测”顺序驱动工具。
- 启动命令 `uvx --from git+…@v0.1.1` 钉死版本；首次启动自动解析并缓存环境。
- 未成年人数据保护说明见上游仓 `docs/privacy/minor-data-protection.md`。

## License

MIT — see [LICENSE](LICENSE).
