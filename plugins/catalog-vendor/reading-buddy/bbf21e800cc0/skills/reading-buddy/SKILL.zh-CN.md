---
name: reading-buddy
description: "当用户想查看本地微信读书的书架、阅读统计与笔记，整理私人读书卡片或写周/月阅读复盘时使用。数据全在本机；另有虚构数据的 demo 模式可用于预览。"
---

# 读书搭子（reading-buddy）

本地优先的微信读书伴侣，通过 MCP 提供（server key `rb`）。引擎钉在不可变
git commit 上、经 npx 启动；数据只落在插件数据目录
（`READING_DATA_DIR` / `READING_CONFIG_DIR`）。
源码：https://github.com/harrylabsj/reading-buddy

## 行为边界（硬性）

- 数据不出本机。绝不向微信读书或任何地方发布、评论、分享；卡片与复盘都是本地文件。
- 绝不索取、复述或输出 `WEREAD_API_KEY` 或任何凭证。服务端从环境变量或它自己的
  0600 配置文件读取。
- 严格区分原文、用户想法与 AI 建议；用户没提供个人理解时只做摘录整理，不伪造感悟。
- `reading_save_card` 是显式写操作：只保存用户看过并确认的卡片/复盘。
- 每个工具都有 `mode`：`live` 是真实数据，`demo` 是独立的虚构示例——预览和演示用 demo。

## 使用流程

1. 先看状态：`reading_ui_state`（live）显示同步状态、目标与当日时长。
2. 找书：`reading_search_books`，按关键词或状态（如 reading）过滤，拿到书 id。
3. 笔记：`reading_get_notes` 传书 id；返回的是已载入部分，不完整要说明；时长缺失
   显示「暂不可用」，不补 0。
4. 卡片：`reading_prepare_card` 用选中的笔记 id + 用户自己的反思起草；展示草稿，
   用户确认后才用 `reading_save_card` 保存。
5. 复盘：`reading_prepare_review`（weekly/monthly）起草，确认后同样保存。
6. `reading_open_dashboard` / `reading_ui_action` 面向能渲染 `ui://` 资源的宿主的
   MCP-App 看板；在普通 MCP 宿主里只返回数据，答问题优先用其它工具。

## 配置说明

live 同步需要微信读书 API Key：用户可在环境变量设 `WEREAD_API_KEY`（MCP 进程会继承），
或用引擎 CLI 的 auth 命令一次性导入。没有 Key 时 demo 模式照常可用。
