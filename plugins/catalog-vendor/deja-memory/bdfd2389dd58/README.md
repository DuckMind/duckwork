# deja-memory for Duckwork

English | [中文](https://github.com/DuckMind/duckwork)

A Duckwork memory provider that answers from the coding sessions already on this
machine: Claude Code, Codex, Cursor, Duckwork itself and the other agents deja
reads, including the months before anything was installed. No model, no API
key, no server. The history is indexed locally by
[deja](https://github.com/vshulcz/deja-vu), a single Go binary.

## Install

deja has to be on PATH first:

```bash
brew install deja-vu        # or: go install github.com/vshulcz/deja-vu/cmd/deja@latest
duckwork plugins install vshulcz/deja-vu/extensions/duckwork
duckwork config set memory.provider deja-memory
```

or pick `deja-memory` in `duckwork memory setup`, which checks for the binary
before it activates the provider.

## What it does

- Before the first turn of a session it hands Duckwork the digest deja's hooks
  give Claude Code and Codex: the recent work in this project and what held.
  After that, only when what was just asked matches something earlier. Most
  turns it adds nothing.
- Three tools: `deja_recall` searches past sessions, `deja_fix` says what was
  run after an error last time, `deja_blame` lists the sessions that edited a
  file.
- An entry Duckwork adds to MEMORY.md or USER.md is kept as a deja note too, so
  it ranks above the sessions around it.

It never writes Duckwork turns anywhere: Duckwork already stores them, and deja
reads that store on its next refresh.

## Same code as `deja install`

`deja install duckwork-auto` writes this provider to `~/.duckwork/plugins/deja-memory`
along with the MCP server and a pre_llm_call hook plugin. The files here are
generated from the same source (`cmd/deja/install_duckwork_memory.go`); the only
difference is that this copy finds deja on PATH instead of having the path
written in. `TestDuckworkExtensionIsTheProviderInstallWrites` fails when the two
drift.
