# GuruSup Brain plugin

Brings GuruSup Brain, your company's memory, into Claude. It bundles the Brain MCP server (OAuth sign-in with your GuruSup account) and a skill that tells Claude to check Brain first for anything about your company.

## Install (Claude Code)

```
/plugin marketplace add gurusup/gurusup-brain-plugin
/plugin install gurusup-brain@gurusup
```

The first Brain call opens a browser to sign in. If you already added the Brain MCP by hand, remove it first (`claude mcp remove gurusup`) so the tools don't show up twice.

## What it sends and where

The plugin runs no local code. Claude calls the Brain MCP server, run by GuruSup, sending the questions and search terms it needs to answer you. You sign in with your GuruSup Brain account through OAuth, and the server only returns what that account is allowed to see. You need a GuruSup Brain account to use it. Privacy policy: https://gurusup.com/privacy#brain

## Contents

| Path | What |
|------|------|
| `.claude-plugin/plugin.json` | Plugin manifest |
| `.claude-plugin/marketplace.json` | Marketplace entry, so the repo installs directly |
| `.mcp.json` | Brain MCP server for Claude, `https://mcp.brain.gurusup.com/mcp` |
| `plugin.json`, `mcp.json` | Same plugin in the [Agent Plugins](https://agent-plugins.org) format, for ChatGPT and other clients |
| `skills/using-brain/` | Check Brain first, follow the `init` contract |

Validate after changes: `claude plugin validate .`. Keep `version` in `.claude-plugin/plugin.json` and `plugin.json` in sync.

Full docs: https://gurusup.com/brain/mcp
