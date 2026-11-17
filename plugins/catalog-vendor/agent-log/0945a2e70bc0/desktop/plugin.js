/**
 * Agent Log — readable agent.log viewer in the status bar.
 *
 * Registers a small chip at the BOTTOM status bar (right side). Click it to open
 * a readable, colour-coded feed of what the agent actually did:
 *   - current model + provider (live, from /api/model/info, log-parsed fallback)
 *   - API calls (tokens / latency / cache), tool runs, turn endings, fallbacks,
 *     warnings and errors — parsed from <duckwork home>/logs/agent.log via host.logs()
 *   - filter tabs, auto-refresh while open, link to the native log view
 *
 * Folder: <duckwork home>/desktop-plugins/agent-log/plugin.js
 * Reload: ⌘K / Ctrl+K → "Reload desktop plugins"
 */

import { host, useValue } from '@duckwork/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useState, useEffect, useRef, forwardRef, useCallback, useMemo } from 'react'

const ID = 'agent-log'
const LOG_FILE = 'agent'
const WINDOW_LINES = 400
const REFRESH_MS = 4000
const REFRESH_OPTIONS = [2000, 4000, 10000, 30000]
// How long the manual refresh keeps its verdict label before reverting.
const STATUS_MS = 5000
// How long the chip's single dot stays RED after a new alert lands.
const FB_ALERT_MS = 30000
// A line this recent counts as a genuine arrival even without a baseline yet
// (3× the chip's poll interval, so one missed tick still catches it).
const ALERT_FRESH_MS = 90000
const MAX_ROWS = 150

/*__PARSER_START__*/
// ---------------------------------------------------------------------------
// Pure parsing & formatting (kept dependency-free so it can be unit-tested in
// Node by extracting this block).
// ---------------------------------------------------------------------------

const LINE_RE = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}),(\d{3}) (DEBUG|INFO|WARNING|ERROR|CRITICAL) (?:\[([^\]]*)\]\s+)?([^:]+): (.*)$/

const COLORS = {
  api_call: 'var(--al-blue)',
  tool_done: 'var(--al-green)',
  tool_error: 'var(--al-red)',
  turn_end: 'var(--al-purple)',
  turn_start: 'var(--al-purple)',
  turn_finished: 'var(--al-purple)',
  prompt: 'var(--al-purple)',
  fallback: 'var(--al-amber)',
  fallback_skip: 'var(--al-muted)',
  call_failed: 'var(--al-red)',
  retry: 'var(--al-amber)',
  stream_error: 'var(--al-red)',
  cred_exhausted: 'var(--al-red)',
  rate_limited: 'var(--al-amber)',
  model_switch: 'var(--al-purple)',
  bg_review: 'var(--al-cyan)',
  // Light-weight auxiliary calls (title gen / approval / vision / compression…):
  // high frequency, no token counts. Muted cyan + hollow dot to sit BELOW
  // bg_review in visual weight — 重评审 vs 轻辅助 must stay distinguishable.
  aux: 'var(--al-cyan-dim)',
  // Provider credential degradation (persistent STATE, not a discrete error):
  // "Copilot token exchange degraded to RAW token …" re-emits every few seconds
  // for hours. Muted amber + hollow dot = a state flag, below real warnings.
  cred_degraded: 'var(--al-orange)',
  error: 'var(--al-red)',
  warning: 'var(--al-amber)',
  info: 'var(--al-muted)',
  debug: 'var(--al-dim)',
  client: 'var(--al-muted)',
}

const FILTERS = {
  all: () => true,
  calls: (ev) => ev.type === 'api_call',
  tools: (ev) => ev.type === 'tool_done' || ev.type === 'tool_error',
  turns: (ev) =>
    ev.type === 'turn_end' ||
    ev.type === 'turn_start' ||
    ev.type === 'turn_finished' ||
    ev.type === 'prompt',
  errors: (ev) =>
    ev.type === 'call_failed' ||
    ev.type === 'stream_error' ||
    ev.type === 'tool_error' ||
    ev.type === 'retry' ||
    ev.type === 'fallback' ||
    ev.type === 'cred_exhausted' ||
    ev.type === 'rate_limited' ||
    ev.level === 'ERROR',
}

function parseLogLine(raw) {
  // Records arrive with a trailing line terminator from the backend reader
  // (readlines() keeps "\n"; the >1MB tail reader re-appends it). Strip any
  // trailing \r / \n so the `$` anchor and kv extraction stay reliable.
  const line = raw ? String(raw).replace(/[\r\n]+$/, '') : raw
  const m = LINE_RE.exec(line)
  if (!m) return null
  const [, date, time, ms, level, session, logger, message] = m
  const grab = (re) => {
    const x = message.match(re)
    return x ? x[1] : null
  }
  const num = (re) => {
    const x = message.match(re)
    return x ? Number(x[1]) : null
  }

  let type = 'info'
  if (/^API call #\d+/.test(message)) type = 'api_call'
  else if (/^API call failed/.test(message)) type = 'call_failed'
  else if (/^Retrying API call/.test(message)) type = 'retry'
  else if (/^Turn ended/.test(message)) type = 'turn_end'
  else if (/^conversation turn/.test(message)) type = 'turn_start'
  else if (/tui turn finished/.test(message)) type = 'turn_finished'
  else if (/tui prompt accepted/.test(message)) type = 'prompt'
  else if (/^tool \S+ completed/.test(message)) type = 'tool_done'
  // Two tool-error spellings coexist in the logs: the executor's
  // "tool web_extract failed (0.02s): …" (lowercase, agent.tool_executor) and
  // the runtime's "Tool search_files returned error (1.10s)" (capitalized).
  // Both are hard failures — classify them together.
  else if (/^Tool \S+ returned error/.test(message) || /^tool \S+ failed \(\d+(\.\d+)?s\)/.test(message)) type = 'tool_error'
  else if (/Fallback activated/.test(message)) type = 'fallback'
  else if (/^Fallback (to|skip)/.test(message)) type = 'fallback_skip'
  else if (/^Streaming failed/.test(message)) type = 'stream_error'
  else if (/Background review complete/.test(message)) type = 'bg_review'
  // Auxiliary model selection, e.g. "Auxiliary approval: using gemini (gemini-2.0-flash) at …".
  // Light aux, no tokens → muted; bg_review stays the loud one. Retry lines
  // ("Auxiliary X: transient transport error …") keep info color — counted, not alerted.
  else if (/^Auxiliary [a-z_]+: using /.test(message)) type = 'aux'
  else if (/OpenAI client (created|closed|retired)/.test(message)) type = 'client'
  // Provider-outage signals (INFO level in source, but they ARE the anomaly):
  // credential pool exhausted = a provider's keys are all spent/blocked, and
  // rate-limit backoff = the endpoint throttling us. Both land in 异常.
  else if (/^credential pool: no available entries/.test(message)) type = 'cred_exhausted'
  else if (/^Rate-limit backoff/.test(message)) type = 'rate_limited'
  // Manual runtime model switch (user-initiated, NOT a fallback):
  // "Model switched in-place: claude-opus-4-8 (custom) -> glm-5.2 (sensenova)"
  else if (/^Model switched in-place/.test(message)) type = 'model_switch'
  // Persistent credential degradation — a STATE re-emitted every few seconds,
  // not a discrete incident. Own type so it stays out of the generic WARNING
  // bucket (it drowned 44 of 64 warning rows in a 400-line window).
  else if (logger === 'agent.credential_pool' && /^Copilot token exchange degraded/.test(message)) type = 'cred_degraded'
  else if (level === 'ERROR') type = 'error'
  else if (level === 'WARNING') type = 'warning'
  else if (level === 'DEBUG') type = 'debug'

  const ev = {
    date,
    time,
    ms,
    level,
    session: session || null,
    logger,
    message,
    raw: line,
    type,
    color: COLORS[type] || COLORS.info,
    model: grab(/model=([^\s]+)/),
    provider: grab(/provider=([^\s]+)/),
    baseUrl: grab(/base_url=([^\s]+)/),
  }

  // API call / turn ended token & latency fields
  ev.callNo = num(/API call #(\d+)/)
  ev.inTok = num(/ in=(\d+)/)
  ev.outTok = num(/ out=(\d+)/)
  ev.totalTok = num(/ total=(\d+)/)
  ev.latency = num(/latency=([\d.]+)s/)
  const cacheM = message.match(/cache=(\d+)\/(\d+) \((\d+)%\)/)
  if (cacheM) {
    ev.cacheUsed = Number(cacheM[1])
    ev.cacheTotal = Number(cacheM[2])
    ev.cachePct = Number(cacheM[3])
  }

  // Turn ended
  ev.reason = grab(/reason=([^\s(]+(?:\([^)]*\))?)/)
  ev.apiCallsUsed = num(/api_calls=(\d+)\/(\d+)/)
  ev.apiCallsBudget = num(/api_calls=\d+\/(\d+)/)
  ev.toolTurns = num(/tool_turns=(\d+)/)
  ev.responseLen = num(/response_len=(\d+)/)

  // Failed calls
  ev.errorType = grab(/error_type=([^\s]+)/)
  ev.attempt = num(/attempt (\d+)\/(\d+)/)
  const sumIdx = message.indexOf('summary=')
  if (sumIdx >= 0) {
    const rest = message.slice(sumIdx + 8)
    ev.summary = rest.split(/ thread=|\n/)[0].trim()
  }

  // Tool runs
  const toolM = message.match(/^tool (\S+) completed \(([\d.]+)s, (\d+) chars\)/)
  if (toolM) {
    ev.tool = toolM[1]
    ev.seconds = Number(toolM[2])
    ev.chars = Number(toolM[3])
  }
  const toolErrM = message.match(/^Tool (\S+) returned error \(([\d.]+)s\)/)
  if (toolErrM) {
    ev.tool = toolErrM[1]
    ev.seconds = Number(toolErrM[2])
  }

  // Background review completion: the one auxiliary task the log records with
  // full token counts — "Background review complete: thread=bg-review calls=6
  // in=139251 out=8545 cache_read=291584 result=skill". Other aux tasks only
  // log "using …", so the window task view is fed by these rows; the official
  // analytics by_task covers the rest (1d+).
  if (ev.type === 'bg_review') {
    ev.bgCalls = num(/ calls=(\d+)/)
    // reuse the in/out extractors carefully: this line spells the cache field
    // "cache_read=" (not "cache=X/Y"), so read it explicitly.
    ev.bgCacheRead = num(/ cache_read=(\d+)/)
    ev.bgResult = grab(/ result=(\S+)/)
  }

  // Auxiliary lines (using OR transient-retry): parse task + model so the row
  // can render "aux: <task> → <model>" and the stats table can count retries.
  if (ev.logger === 'agent.auxiliary_client' && /^Auxiliary ([a-z_]+):/.test(message)) {
    ev.auxTask = grab(/^Auxiliary ([a-z_]+):/)
    const am = message.match(/^Auxiliary [a-z_]+: using (\S+)(?: \(([^)]+)\))?/)
    if (am) {
      ev.auxProvider = am[1]
      ev.auxModel = am[2] || am[1]
    }
    if (/^Auxiliary [a-z_]+: transient transport error/.test(message)) ev.auxRetry = true
  }

  // Copilot token-exchange degradation: record the degraded token form so the
  // row can read "凭据降级（RAW token）" without expanding the raw message.
  if (ev.type === 'cred_degraded') ev.degradedTo = grab(/degraded to (\S+) token/i)

  // Fallback activated: A → B (provider)
  const fbM = message.match(/Fallback activated:\s*([^→]+?)\s*→\s*([^(]+?)\s*\(([^)]+)\)/)
  if (fbM) {
    ev.from = fbM[1].trim()
    ev.to = fbM[2].trim()
    ev.toProvider = fbM[3].trim()
  }

  // Model switched in-place: A (provider) -> B (provider) — user-initiated
  // runtime switch (NOT a fallback). Note the ASCII "->" vs fallback's "→".
  const msM = message.match(/^Model switched in-place:\s*(.+?)\s*\(([^)]+)\)\s*->\s*(.+?)\s*\(([^)]+)\)/)
  if (msM) {
    ev.from = msM[1].trim()
    ev.fromProvider = msM[2].trim()
    ev.to = msM[3].trim()
    ev.toProvider = msM[4].trim()
  }

  // conversation turn: capture the user message preview
  const msgIdx = message.indexOf("msg='")
  if (msgIdx >= 0) {
    const rest = message.slice(msgIdx + 5)
    const end = rest.lastIndexOf("'")
    ev.msgPreview = end > 0 ? rest.slice(0, end) : rest
  }

  // A short human-readable title for the row (Chinese, from STRINGS by the caller)
  return ev
}

function fmtK(n) {
  if (n == null) return '—'
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}G`
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return `${n}`
}

function truncate(s, max) {
  if (s == null) return ''
  const str = String(s)
  return str.length > max ? `${str.slice(0, max)}…` : str
}

// Join the pieces of a copied stats row with " · ", dropping empty ones: a
// provider the backend recorded as "" (aux usage rows in session_model_usage)
// must not leave a dangling separator, and a row with no provider still copies
// its full metrics instead of degrading to a bare model name.
function modelCopyText(model, provider, pairs) {
  return [model, provider, ...(pairs || [])]
    .filter((p) => p != null && String(p) !== '')
    .join(' · ')
}

const STRINGS = {
  zh: {
    title: 'Agent 日志',
    chipTip: '查看模型、提供商与最近动作',
    fbAlert: '检测到新回退',
    alertCredExhausted: '凭据池耗尽（供应商密钥不可用）',
    session: '会话',
    model: '模型',
    provider: '提供商',
    updatedAt: '更新于',
    linesSuffix: '最近 400 行',
    events: '条事件',
    auto: '自动刷新',
    refreshEvery: '自动刷新间隔',
    refresh: '刷新',
    refreshTip: '立即重新读取 agent.log，并重置自动刷新计时',
    refreshing: '刷新中…',
    refreshDone: '已刷新',
    refreshNoNew: '无新增日志',
    refreshNew: (n) => `+${n} 条新`,
    nativeLogs: '原生日志',
    close: '关闭',
    copyHint: '点击行复制原始日志',
    copied: '已复制',
    noData: '暂无日志',
    noDataHint: '打开后会自动读取 agent.log',
    loadError: '读取日志失败',
    older: '更早的日志省略',
    loading: '加载中…',
    busy: '工作中',
    idle: '空闲',
    // stats
    calls: '调用',
    input: '输入',
    output: '输出',
    tools: '工具',
    fallbacks: '回退',
    errors: '错误',
    warns: '警告',
    // filter tabs
    tabAll: '全部',
    tabCalls: '调用',
    tabTools: '工具',
    tabTurns: '轮次',
    tabErrors: '异常',
    // event titles
    eApiCall: (n) => `模型调用 #${n}`,
    copiedBadge: '✓ 已复制',
    statsWindowLines: (n) => `最近 ${n} 行日志`,
    eToolDone: (name, secs, chars) => `工具 ${name} · ${secs}s · ${fmtK(chars)} 字符`,
    eToolError: (name, secs) => `工具 ${name} 出错 · ${secs}s`,
    eTurnEnd: '回合结束',
    eTurnStart: '新回合',
    eTurnFinished: '回合完成',
    ePrompt: '收到用户消息',
    eFallback: (from, to) => `回退 ${from} → ${to}`,
    eFallbackSkip: '回退跳过',
    eModelSwitch: (from, to) => `切换模型 ${from} → ${to}`,
    eCredExhausted: '凭据池耗尽',
    eRateLimited: '触发限流',
    eCallFailed: (a, b) => `调用失败 (${a}/${b})`,
    eRetry: '重试调用',
    eStreamError: '流式输出失败',
    eBgReview: '后台评审完成',
    eAux: (task, model) => `辅助 ${task} → ${model}`,
    eCredDegraded: (form) => `Copilot 凭据降级（${form} token）`,
    repeatTip: (n, a, b) => `持续状态重复 ×${n}（${a} → ${b}）— 已折叠为一行，点击复制原文`,
    eClient: '客户端连接',
    eError: '错误',
    eWarning: '警告',
    eInfo: '信息',
    eDebug: '调试',
    reason: '原因',
    replyLen: '回复',
    toolTurns: '工具轮',
    totalTok: '总计',
    cache: '缓存',
    charsShort: '字符',
    // fallback for unknown type
    eUnknown: '日志',
    // stats tab
    tabStats: '统计',
    statsModelTitle: '模型消耗',
    statsToolTitle: '工具调用',
    statsCalls: '调用',
    statsIn: '输入',
    statsOut: '输出',
    statsTotal: '总计',
    statsAvgLatency: '平均延迟',
    statsSuccess: '成功',
    statsFail: '失败',
    statsRate: '成功率',
    statsFallback: '回退',
    statsNoData: '暂无统计数据',
    statsWindow: '基于当前日志窗口',
    statsErrorTitle: '异常概览',
    statsErrLevel: '错误',
    statsWarnLevel: '警告',
    statsCallFailed: '调用失败',
    statsStreamFailed: '流式失败',
    statsToolError: '工具报错',
    statsFallback: '回退',
    statsSwitch: '切入',
    statsSwitchHint: '手动切入次数（非回退）',
    statsRetry: '重试',
    statsCredExhausted: '凭据耗尽',
    statsRateLimited: '限流',
    statsCredDegraded: '凭据降级',
    statsCredDegradedHint: '持续的凭据降级状态（如 Copilot exchange 不可用）发生次数；重复行已在事件流折叠，不计入「警告」',
    statsRange: '时间范围',
    rangeWindow: '当前时段',
    range1d: '1天',
    range3d: '3天',
    range7d: '7天',
    range30d: '30天',
    range90d: '90天',
    statsLoading: '加载中…',
    statsCost: '费用',
    statsSessions: '会话',
    statsPct: '占比',
    statsTotalIn: '总输入',
    statsCacheHit: '缓存命中',
    statsNoAnalytics: '官方接口暂无数据',
    // task (purpose) breakdown — auxiliary usage from /api/analytics/usage by_task
    statsTaskTitle: '用途消耗',
    statsTaskCalls: '调用',
    statsTaskRetries: '重试',
    statsTaskRetriesHint: '辅助任务 transient transport error 重试次数（不告警，仅查询）',
    statsTaskIn: '输入',
    statsTaskOut: '输出',
    statsTaskCost: '费用',
    statsTaskModels: '模型',
    statsTaskWindowHint: '辅助任务（视觉/压缩/审批等）的明细请切到 1 天及以上查看',
    statsCardsHint: '各卡片独立计数，不可求和',
    errsBreakdown: (base, tool, total) => `错误（含工具失败）${total} = 基础错误 ${base} + 工具失败 ${tool}；fallback/retry 另计`,
    taskMain: '主对话',
    taskVision: '视觉',
    taskCompression: '压缩',
    taskSkillsHub: '技能中心',
    taskApproval: '审批',
    taskMcp: 'MCP',
    taskTitleGen: '标题生成',
    taskReview: '评审',
    taskCurator: '维护器',
    taskBgReview: '后台评审',
  },
  en: {
    title: 'Agent Log',
    chipTip: 'View model, provider & recent activity',
    fbAlert: 'New fallback detected',
    alertCredExhausted: 'credential pool exhausted (provider keys unusable)',
    session: 'Session',
    model: 'Model',
    provider: 'Provider',
    updatedAt: 'Updated',
    linesSuffix: 'last 400 lines',
    events: 'events',
    auto: 'Auto-refresh',
    refreshEvery: 'Auto-refresh interval',
    refresh: 'Refresh',
    refreshTip: 'Re-read agent.log now, and restart the auto-refresh countdown',
    refreshing: 'refreshing…',
    refreshDone: 'refreshed',
    refreshNoNew: 'no new lines',
    refreshNew: (n) => `+${n} new`,
    nativeLogs: 'Native logs',
    close: 'Close',
    copyHint: 'click a row to copy raw line',
    copied: 'copied',
    noData: 'No logs yet',
    noDataHint: 'agent.log is read automatically',
    loadError: 'Failed to read logs',
    older: 'older events omitted',
    loading: 'Loading…',
    busy: 'Working',
    idle: 'Idle',
    calls: 'calls',
    input: 'in',
    output: 'out',
    tools: 'tools',
    fallbacks: 'fallbacks',
    errors: 'errors',
    warns: 'warns',
    tabAll: 'All',
    tabCalls: 'Calls',
    tabTools: 'Tools',
    tabTurns: 'Turns',
    tabErrors: 'Issues',
    eApiCall: (n) => `API call #${n}`,
    copiedBadge: '✓ copied',
    statsWindowLines: (n) => `last ${n} log lines`,
    eToolDone: (name, secs, chars) => `Tool ${name} · ${secs}s · ${fmtK(chars)} chars`,
    eToolError: (name, secs) => `Tool ${name} error · ${secs}s`,
    eTurnEnd: 'Turn ended',
    eTurnStart: 'New turn',
    eTurnFinished: 'Turn finished',
    ePrompt: 'User message',
    eFallback: (from, to) => `Fallback ${from} → ${to}`,
    eFallbackSkip: 'Fallback skipped',
    eModelSwitch: (from, to) => `Model switch ${from} → ${to}`,
    eCredExhausted: 'Credentials exhausted',
    eRateLimited: 'Rate limited',
    eCallFailed: (a, b) => `Call failed (${a}/${b})`,
    eRetry: 'Retrying call',
    eStreamError: 'Stream failed',
    eBgReview: 'Background review done',
    eAux: (task, model) => `aux ${task} → ${model}`,
    eCredDegraded: (form) => `Copilot cred degraded (${form} token)`,
    repeatTip: (n, a, b) => `Repeated state ×${n} (${a} → ${b}) — collapsed to one row; click to copy the raw line`,
    eClient: 'Client',
    eError: 'Error',
    eWarning: 'Warning',
    eInfo: 'Info',
    eDebug: 'Debug',
    reason: 'reason',
    replyLen: 'reply',
    toolTurns: 'tool turns',
    totalTok: 'total',
    cache: 'cache',
    charsShort: 'chars',
    eUnknown: 'Log',
    // stats tab
    tabStats: 'Stats',
    statsModelTitle: 'Model usage',
    statsToolTitle: 'Tool usage',
    statsCalls: 'calls',
    statsIn: 'in',
    statsOut: 'out',
    statsTotal: 'total',
    statsAvgLatency: 'avg latency',
    statsSuccess: 'ok',
    statsFail: 'fail',
    statsRate: 'rate',
    statsFallback: 'fallback',
    statsNoData: 'No stats yet',
    statsWindow: 'based on current log window',
    statsErrorTitle: 'Issues',
    statsErrLevel: 'errors',
    statsWarnLevel: 'warns',
    statsCallFailed: 'call failed',
    statsStreamFailed: 'stream failed',
    statsToolError: 'tool error',
    statsFallback: 'fallback',
    statsSwitch: 'switch',
    statsSwitchHint: 'manual switch-ins (not fallback)',
    statsRetry: 'retry',
    statsCredExhausted: 'credential',
    statsRateLimited: 'rate limit',
    statsCredDegraded: 'cred degraded',
    statsCredDegradedHint: 'occurrences of a persistent credential degradation (e.g. Copilot exchange unavailable); repeated rows are collapsed in the feed and excluded from the warns pill',
    statsRange: 'Range',
    rangeWindow: 'Live',
    range1d: '1d',
    range3d: '3d',
    range7d: '7d',
    range30d: '30d',
    range90d: '90d',
    statsLoading: 'Loading…',
    statsCost: 'Cost',
    statsSessions: 'Sessions',
    statsPct: 'Pct',
    statsTotalIn: 'Total In',
    statsCacheHit: 'Cache Hit',
    statsNoAnalytics: 'No analytics data',
    statsTaskTitle: 'Usage by task',
    statsTaskCalls: 'calls',
    statsTaskRetries: 'retry',
    statsTaskRetriesHint: 'aux transient transport error retries (no alert, lookup only)',
    statsTaskIn: 'in',
    statsTaskOut: 'out',
    statsTaskCost: 'cost',
    statsTaskModels: 'models',
    statsTaskWindowHint: 'Auxiliary task details (vision / compression / approval…) are available from 1d+',
    statsCardsHint: 'Cards counted independently — do not sum',
    errsBreakdown: (base, tool, total) => `Errors (incl. tool failures) ${total} = base ${base} + tool ${tool}; fallback/retry counted separately`,
    taskMain: 'Main chat',
    taskVision: 'Vision',
    taskCompression: 'Compression',
    taskSkillsHub: 'Skills Hub',
    taskApproval: 'Approval',
    taskMcp: 'MCP',
    taskTitleGen: 'Title gen',
    taskReview: 'Review',
    taskCurator: 'Curator',
    taskBgReview: 'Background review',
  },
}

function eventTitle(ev, t) {
  switch (ev.type) {
    case 'api_call':
      return t.eApiCall(ev.callNo ?? '')
    case 'tool_done':
      return t.eToolDone(ev.tool ?? '?', ev.seconds ?? 0, ev.chars ?? 0)
    case 'tool_error':
      return t.eToolError(ev.tool ?? '?', ev.seconds ?? 0)
    case 'turn_end':
      return t.eTurnEnd
    case 'turn_start':
      return t.eTurnStart
    case 'turn_finished':
      return t.eTurnFinished
    case 'prompt':
      return t.ePrompt
    case 'fallback':
      return t.eFallback(ev.from ?? '', ev.to ?? '')
    case 'fallback_skip':
      return t.eFallbackSkip
    case 'model_switch':
      return t.eModelSwitch(ev.from ?? '', ev.to ?? '')
    case 'cred_exhausted':
      return t.eCredExhausted
    case 'rate_limited':
      return t.eRateLimited
    case 'call_failed':
      return t.eCallFailed(ev.attempt ?? '?', 3)
    case 'retry':
      return t.eRetry
    case 'stream_error':
      return t.eStreamError
    case 'bg_review':
      return t.eBgReview
    case 'aux':
      return t.eAux(ev.auxTask ?? '?', ev.auxProvider ?? '')
    case 'cred_degraded':
      return t.eCredDegraded(ev.degradedTo ?? 'RAW')
    case 'client':
      return t.eClient
    case 'error':
      return t.eError
    case 'warning':
      return t.eWarning
    case 'debug':
      return t.eDebug
    default:
      return t.eInfo
  }
}

// Auxiliary "task" keys (session_model_usage.task / analytics by_task[].task)
// map to localized labels; unknown keys fall back to the raw key with underscores
// replaced by spaces, so newly added backend tasks still read sensibly.
function taskLabel(task, t) {
  if (!task) return ''
  const map = {
    vision: t.taskVision,
    compression: t.taskCompression,
    skills_hub: t.taskSkillsHub,
    approval: t.taskApproval,
    mcp: t.taskMcp,
    title_generation: t.taskTitleGen,
    review: t.taskReview,
    curator: t.taskCurator,
    background_review: t.taskBgReview,
  }
  return map[task] || String(task).replace(/_/g, ' ')
}

// --- Repeated-STATE collapse -------------------------------------------------
// A few log lines describe a persistent state and are re-emitted every few
// seconds (Copilot token-exchange degradation: ~44 identical rows per 400-line
// window, running for hours). One row per emission is pure noise, so repeats of
// a COLLAPSIBLE type fold into the newest row, carrying a count + time span.
// Only types whose repetition carries NO new information belong here — discrete
// events (errors, retries, API calls, tools) keep one row per occurrence.
const COLLAPSIBLE_TYPES = new Set(['cred_degraded'])

// `events` arrive newest-first, so the row kept is the newest occurrence;
// spanFirst/spanLast cover the whole collapsed span (oldest → newest).
function collapseRepeats(events) {
  if (!Array.isArray(events) || events.length === 0) return events || []
  const out = []
  const seen = new Map()
  for (const ev of events) {
    if (!COLLAPSIBLE_TYPES.has(ev.type)) { out.push(ev); continue }
    const key = `${ev.type}::${ev.message}`
    const ts = `${ev.date} ${ev.time}`
    const hit = seen.get(key)
    if (!hit) {
      const row = { ...ev, repeatCount: 1, spanFirst: ts, spanLast: ts }
      seen.set(key, row)
      out.push(row)
    } else {
      hit.repeatCount++
      hit.spanFirst = ts // walking newest → oldest, so this end is the older one
    }
  }
  return out
}

// "19:09–20:08" from full "YYYY-MM-DD HH:MM:SS" stamps (same clock day assumed);
// returns '' when either stamp is missing so callers can skip the badge.
function shortSpan(from, to) {
  const hm = (s) => (typeof s === 'string' && s.length >= 16 ? s.slice(11, 16) : '')
  const a = hm(from)
  const b = hm(to)
  if (!a || !b) return ''
  return a === b ? a : `${a}–${b}`
}

// Epoch ms of a parsed event (log stamps are local time, as the reader gives them).
function evEpoch(ev) {
  return new Date(`${ev.date} ${ev.time}`).getTime() + Number(ev.ms || 0)
}

// --- Alert classes (drive the chip's single red dot) -------------------------
// TAKE OVER the dot only if the class is: rare, edge-triggered, actionable and
// NOT self-healing — otherwise the light parks on red forever.
//   cred_exhausted = a provider's keys are all spent (needs a human: rotate/add)
//   fallback       = a re-route already happened (the one you want to notice)
// Deliberately EXCLUDED (see the census in the skill notes): call_failed /
// stream_error / tool_error / rate_limited (retry-class, self-healing or noisy),
// warning (mixed bucket), and every persistent state such as cred_degraded
// (re-emits forever ⇒ would never stop blinking). One dot = one alert channel,
// so each addition dilutes it; the class name goes in the tooltip, not a new dot.
const ALERT_TYPES = ['cred_exhausted', 'fallback']

// Alert bookkeeping shared by the chip's 30s poll and the popover's 4s refresh —
// BOTH watch for the same classes and only whichever is awake reports. `seen` is
// the caller-owned map {type: epochMs} of what was already known; `newest` holds
// the newest timestamp found per class in the current pass. Mutates `seen` and
// returns the class to alert on (the newest NEWLY seen one) or null.
//
// A class's FIRST sighting is normally just the startup baseline (an OLD line
// must not blink the dot on first paint). BUT if that first sighting is FRESH —
// stamped within `freshMs` of `nowMs` — it is a genuine arrival and DOES alert:
// otherwise the first fallback/cred-exhaustion after a plugin reload would be
// silently swallowed (a real false negative for a rare, actionable event).
// Callers that pass no clock (nowMs == null) keep the pure baseline behaviour.
function reportAlerts(seen, newest, nowMs, freshMs) {
  let reason = null
  let best = -1
  for (const tp of ALERT_TYPES) {
    const ts = newest[tp]
    if (ts == null) continue
    const prev = seen[tp]
    const isNew = prev == null
      ? (nowMs != null && ts <= nowMs && nowMs - ts <= (freshMs || 0))
      : ts > prev
    if (isNew && ts > best) {
      reason = tp
      best = ts
    }
    // Advance the baseline on new stamps only — a rotated log (older stamp)
    // must never rewind it, or the same old line would re-alert forever.
    if (prev == null || ts > prev) seen[tp] = ts
  }
  return reason
}

// Human label for the alert that owns the dot (the dot itself cannot say why).
function alertLabel(reason, t) {
  if (reason === 'cred_exhausted') return t.alertCredExhausted
  if (reason === 'fallback') return t.fbAlert
  return null
}
/*__PARSER_END__*/

function getLocale() {
  try {
    // The SDK exposes no host.i18n — the app writes the live language to
    // document.documentElement.lang on every switch (applyDocumentLocale).
    const l = typeof document !== 'undefined' ? document.documentElement.lang : ''
    if (typeof l === 'string') {
      if (l.startsWith('zh')) return 'zh'
      if (l.startsWith('en')) return 'en'
    }
  } catch {}
  return 'en'
}

function Dot({ color, pulse, hollow }) {
  return jsx('span', {
    className: 'inline-block rounded-full flex-shrink-0' + (hollow ? ' w-1 h-1' : ' w-1.5 h-1.5'),
    style: {
      ...(hollow
        ? { border: `1.5px solid ${color}`, backgroundColor: 'transparent' }
        : { backgroundColor: color }),
      ...(pulse
        ? { animation: 'agent-log-pulse 1.2s ease-in-out infinite' }
        : {}),
    },
  })
}

// Inject the tiny pulse keyframe once (DOM work only — no module imports beyond
// the sandbox whitelist). Safe to call on every mount; guarded by style id.
const PULSE_STYLE_ID = 'agent-log-pulse-keyframes'
// ---------------------------------------------------------------------------
// Theme tokens. The plugin renders INSIDE the Duckwork desktop app, so it has to
// follow the app's theme (Appearance → light / dark / system, and any custom
// skin) instead of hardcoding a dark palette — hardcoded dark-on-dark was fine
// in dark mode and made every label invisible in light mode.
//
// The app sets `.dark` on <html> (`root.classList.toggle('dark', isDark)` in
// themes/context.tsx), which is exactly what its own CSS keys off, so this
// needs no JS, no listener and no reload: the switch follows the class.
//
// DARK keeps the plugin's original hexes byte-for-byte (no visual regression);
// LIGHT mirrors the app's own light tokens (--ui-text-*, --ui-blue, …), so it
// also follows a custom skin's palette.
// ---------------------------------------------------------------------------
const THEME_STYLE_ID = 'agent-log-theme-vars'
const THEME_CSS = `
.agent-log-scope {
  --al-panel: #1e1e22;
  --al-text: #e6e6e6;
  --al-secondary: #b0b0b8;
  --al-muted: #8a8f9d;
  --al-dim: #6e7681;
  --al-faint: #3a3a42;
  --al-fill: rgba(255,255,255,0.06);
  --al-fill-soft: rgba(255,255,255,0.04);
  --al-line: rgba(255,255,255,0.06);
  --al-line-strong: rgba(255,255,255,0.1);
  --al-on-accent: #0d1117;
  --al-blue: #58a6ff;
  --al-green: #3fb950;
  --al-red: #f85149;
  --al-amber: #d29922;
  --al-purple: #a371f7;
  --al-cyan: #39c5cf;
  --al-cyan-dim: #5f8f92;
  --al-orange: #c08a3e;
}
:root:not(.dark) .agent-log-scope {
  --al-panel: var(--dt-popover, #ffffff);
  --al-text: var(--ui-text-primary, #16181d);
  --al-secondary: var(--ui-text-secondary, #3f434d);
  --al-muted: color-mix(in srgb, var(--ui-base, #1f2328) 67%, transparent);
  --al-dim: var(--ui-text-tertiary, #6b7280);
  --al-faint: color-mix(in srgb, var(--ui-base, #16181d) 24%, transparent);
  --al-fill: color-mix(in srgb, var(--ui-base, #16181d) 7%, transparent);
  --al-fill-soft: color-mix(in srgb, var(--ui-base, #16181d) 4%, transparent);
  --al-line: color-mix(in srgb, var(--ui-base, #16181d) 9%, transparent);
  --al-line-strong: color-mix(in srgb, var(--ui-base, #16181d) 14%, transparent);
  --al-on-accent: #fcfcfc;
  --al-blue: var(--ui-blue, #0053fd);
  /* Hues that carry 10-11px text are deepened toward the ink until they clear
     ~4.8:1 on the light panel — the app's raw light palette is tuned for large
     fills, not for 10px labels (amber raw = 3.1:1, i.e. worse than dark mode).
     Ratios come from the WCAG solver in verify_theme.js; the hue survives, the
     ordering within the palette is preserved. */
  --al-green: color-mix(in srgb, var(--ui-green, #1f8a65) 68%, var(--ui-text-primary, #1f2328));
  --al-red: var(--ui-red, #cf2d56);
  --al-amber: color-mix(in srgb, var(--ui-yellow, #c08532) 52%, var(--ui-text-primary, #1f2328));
  --al-purple: color-mix(in srgb, var(--ui-purple, #9e94d5) 57%, var(--ui-text-primary, #1f2328));
  --al-cyan: color-mix(in srgb, var(--ui-cyan, #4c7f8c) 69%, var(--ui-text-primary, #1f2328));
  --al-cyan-dim: color-mix(in srgb, var(--ui-cyan, #4c7f8c) 90%, var(--ui-text-primary, #1f2328));
  --al-orange: color-mix(in srgb, var(--ui-orange, #db704b) 60%, var(--ui-text-primary, #1f2328));
}
`

function ensureThemeCss() {
  try {
    if (typeof document === 'undefined' || document.getElementById(THEME_STYLE_ID)) return
    const style = document.createElement('style')
    style.id = THEME_STYLE_ID
    style.textContent = THEME_CSS
    document.head.appendChild(style)
  } catch {}
}

function ensurePulseKeyframes() {
  try {
    if (typeof document === 'undefined' || document.getElementById(PULSE_STYLE_ID)) return
    const style = document.createElement('style')
    style.id = PULSE_STYLE_ID
    style.textContent = '@keyframes agent-log-pulse { 0%,100% { opacity: 1 } 50% { opacity: 0.25 } }'
    document.head.appendChild(style)
  } catch {}
}

function StatPill({ label, value, color, title }) {
  return jsxs('span', {
    title,
    className:
      'inline-flex items-center gap-1 px-1.5 py-px rounded text-[10px] font-mono bg-(--chrome-action-hover) whitespace-nowrap',
    children: [
      jsx('span', { className: 'opacity-60', children: label }),
      jsx('span', { style: color ? { color } : undefined, children: value }),
    ],
  })
}

// --- One parsed event rendered as a readable row ---
// Left-click a row to copy the RAW log line to the clipboard (for bug reports,
// searches, pasting into issues). A brief "copied" badge shows the feedback.
function fallbackCopy(text) {
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  } catch {}
}

function EventRow({ ev, t }) {
  const [copied, setCopied] = useState(false)
  const copyTimerRef = useRef(null)
  useEffect(() => () => { if (copyTimerRef.current) clearTimeout(copyTimerRef.current) }, [])

  const handleCopy = () => {
    if (!copyText) return
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(copyText).catch(() => fallbackCopy(copyText))
      } else {
        fallbackCopy(copyText)
      }
    } catch {
      fallbackCopy(copyText)
    }
    setCopied(true)
    if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
    copyTimerRef.current = setTimeout(() => setCopied(false), 1200)
  }

  const title = eventTitle(ev, t)

  // Collapsed rows (see collapseRepeats) carry a repeat count: append the folded
  // span to the copied text so pasted evidence shows what was merged.
  const copyText = ev.repeatCount > 1
    ? `${ev.raw}\n  [collapsed: ×${ev.repeatCount} identical lines, ${ev.spanFirst} → ${ev.spanLast}]`
    : ev.raw

  let detail = null
  let meta = null

  if (ev.type === 'api_call') {
    detail = jsxs('span', {
      className: 'flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[10px] text-(--ui-text-tertiary)',
      children: [
        jsxs('span', {
          children: [
            jsx('span', { className: 'opacity-60', children: `${t.input} ` }),
            jsx('span', { style: { color: 'var(--al-blue)' }, children: fmtK(ev.inTok) }),
          ],
        }),
        jsxs('span', {
          children: [
            jsx('span', { className: 'opacity-60', children: `${t.output} ` }),
            jsx('span', { style: { color: 'var(--al-green)' }, children: fmtK(ev.outTok) }),
          ],
        }),
        ev.totalTok != null &&
          jsxs('span', {
            children: [
              jsx('span', { className: 'opacity-60', children: `${t.totalTok} ` }),
              jsx('span', { children: fmtK(ev.totalTok) }),
            ],
          }),
        ev.latency != null &&
          jsxs('span', {
            children: [
              jsx('span', { className: 'opacity-60', children: '⏱ ' }),
              jsx('span', { children: `${ev.latency}s` }),
            ],
          }),
        ev.cachePct != null &&
          jsxs('span', {
            children: [
              jsx('span', { className: 'opacity-60', children: `${t.cache} ` }),
              jsx('span', { style: { color: 'var(--al-purple)' }, children: `${ev.cachePct}%` }),
            ],
          }),
      ],
    })
  } else if (ev.type === 'turn_end') {
    detail = jsxs('span', {
      className: 'flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[10px] text-(--ui-text-tertiary)',
      children: [
        ev.reason &&
          jsxs('span', {
            children: [
              jsx('span', { className: 'opacity-60', children: `${t.reason} ` }),
              jsx('span', { children: ev.reason }),
            ],
          }),
        ev.responseLen != null &&
          jsxs('span', {
            children: [
              jsx('span', { className: 'opacity-60', children: `${t.replyLen} ` }),
              jsx('span', { children: `${fmtK(ev.responseLen)}` }),
            ],
          }),
        ev.toolTurns != null &&
          jsxs('span', {
            children: [
              jsx('span', { className: 'opacity-60', children: `${t.toolTurns} ` }),
              jsx('span', { children: ev.toolTurns }),
            ],
          }),
      ],
    })
  } else if (ev.type === 'call_failed' || ev.type === 'retry') {
    const parts = []
    if (ev.errorType) {
      parts.push(
        jsx('span', {
          key: 'et',
          style: { color: 'var(--al-red)' },
          children: ev.errorType,
        })
      )
    }
    if (ev.summary) {
      parts.push(
        jsx('span', { key: 'sum', className: 'opacity-80', children: truncate(ev.summary, 80) })
      )
    }
    detail = jsx('span', {
      className: 'flex flex-wrap items-center gap-x-2 font-mono text-[10px] text-(--ui-text-tertiary)',
      children: parts,
    })
  } else if (ev.type === 'fallback' || ev.type === 'model_switch') {
    detail = jsxs('span', {
      className: 'font-mono text-[10px] text-(--ui-text-tertiary)',
      children: [
        ev.toProvider &&
          jsx('span', {
            className: 'px-1 py-px rounded bg-(--chrome-action-hover) text-(--ui-text-secondary)',
            children: ev.toProvider,
          }),
      ],
    })
  } else if (ev.type === 'turn_start') {
    detail = ev.msgPreview
      ? jsx('span', {
          className: 'text-[10px] text-(--ui-text-tertiary) break-all',
          title: ev.msgPreview,
          children: truncate(ev.msgPreview, 100),
        })
      : null
  } else if (ev.type === 'prompt') {
    detail = null
  } else if (ev.type === 'error' || ev.type === 'warning' || ev.type === 'stream_error' || ev.type === 'cred_exhausted' || ev.type === 'rate_limited') {
    detail = jsx('span', {
      className: 'text-[10px] text-(--ui-text-tertiary) break-all font-mono',
      title: ev.message,
      children: truncate(ev.message, 130),
    })
  } else if (ev.type === 'tool_error') {
    detail = jsx('span', {
      className: 'text-[10px] text-(--ui-text-tertiary) break-all font-mono',
      title: ev.message,
      children: truncate(ev.message, 100),
    })
  } else if (ev.type === 'info' || ev.type === 'debug' || ev.type === 'client' || ev.type === 'fallback_skip') {
    detail = jsx('span', {
      className: 'text-[10px] text-(--ui-text-tertiary) break-all',
      title: ev.message,
      children: truncate(ev.message, 120),
    })
  } else if (ev.type === 'bg_review') {
    detail = jsxs('span', {
      className: 'flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[10px] text-(--ui-text-tertiary)',
      children: [
        ev.bgCalls != null && jsxs('span', { key: 'c', children: [
          jsx('span', { className: 'opacity-60', children: `${t.statsCalls} ` }),
          jsx('span', { children: ev.bgCalls }),
        ]}),
        ev.inTok != null && jsxs('span', { key: 'i', children: [
          jsx('span', { className: 'opacity-60', children: `${t.statsTaskIn} ` }),
          jsx('span', { style: { color: 'var(--al-blue)' }, children: fmtK(ev.inTok) }),
        ]}),
        ev.outTok != null && jsxs('span', { key: 'o', children: [
          jsx('span', { className: 'opacity-60', children: `${t.statsTaskOut} ` }),
          jsx('span', { style: { color: 'var(--al-green)' }, children: fmtK(ev.outTok) }),
        ]}),
        ev.bgCacheRead != null && (ev.inTok + ev.bgCacheRead) > 0 && jsxs('span', { key: 'cr', children: [
          jsx('span', { className: 'opacity-60', children: `${t.statsCacheHit} ` }),
          // This line's in= is NET input summed across calls and cache_read= is
          // the cumulative cache (each call resends context, so cache_read can
          // exceed net input — the 209% trap). Total prompt = in + cache_read,
          // matching the analytics-side normalization, NOT the API-call line
          // where `in=` already includes the cache.
          jsx('span', { style: { color: 'var(--al-purple)' }, children: `${((ev.bgCacheRead / (ev.inTok + ev.bgCacheRead)) * 100).toFixed(0)}%` }),
        ]}),
        ev.bgResult && jsx('span', { key: 'r', className: 'opacity-80', children: ev.bgResult }),
      ],
    })
  }

  if (ev.model || ev.provider) {
    meta = jsxs('span', {
      className: 'flex items-center gap-1 font-mono text-[9px] text-(--ui-text-tertiary) opacity-70',
      children: [
        ev.provider &&
          jsx('span', {
            className: 'px-1 py-px rounded bg-(--chrome-action-hover) flex-shrink-0',
            children: ev.provider,
          }),
        ev.model && jsx('span', { className: 'truncate', children: ev.model }),
      ],
    })
  }

  return jsxs('div', {
    onClick: handleCopy,
    title: copied ? `✓ ${t.copied}` : t.copyHint,
    className:
      'px-3 py-1.5 border-b border-(--ui-stroke-secondary) last:border-b-0 ' +
      'hover:bg-(--chrome-action-hover) cursor-pointer select-none',
    children: [
      jsxs('div', {
        className: 'flex items-start gap-2 min-w-0',
        children: [
          jsx('span', {
            className: 'font-mono text-[10px] text-(--ui-text-tertiary) mt-0.5 flex-shrink-0',
            children: ev.time,
          }),
          jsx('span', {
            className: 'mt-1 flex-shrink-0',
            children: jsx(Dot, { color: ev.color, hollow: ev.type === 'aux' || ev.type === 'cred_degraded' }),
          }),
          jsxs('div', {
            className: 'flex-1 min-w-0',
            children: [
              jsxs('div', {
                className: 'flex items-center gap-1.5 min-w-0',
                children: [
                  jsx('span', {
                    className: 'text-[11px] font-medium truncate',
                    style: { color: ev.color },
                    children: title,
                  }),
                  jsx('span', {
                    className: 'text-[9px] text-(--ui-text-tertiary) opacity-60 truncate flex-shrink-0 max-w-[140px]',
                    children: ev.logger,
                  }),
                  // Collapsed repeated-state badge: how many identical emissions
                  // were folded into this row, and over what span.
                  ev.repeatCount > 1 &&
                    jsx('span', {
                      className: 'text-[9px] font-mono flex-shrink-0 px-1 py-px rounded bg-(--chrome-action-hover)',
                      style: { color: ev.color },
                      title: t.repeatTip(ev.repeatCount, ev.spanFirst, ev.spanLast),
                      children: `×${ev.repeatCount}${shortSpan(ev.spanFirst, ev.spanLast) ? ` · ${shortSpan(ev.spanFirst, ev.spanLast)}` : ''}`,
                    }),
                  copied &&
                    jsx('span', {
                      className: 'text-[9px] font-mono flex-shrink-0',
                      style: { color: 'var(--al-green)' },
                      children: `✓ ${t.copied}`,
                    }),
                ],
              }),
              detail ? jsx('div', { className: 'mt-0.5 min-w-0', children: detail }) : null,
              meta ? jsx('div', { className: 'mt-0.5 min-w-0', children: meta }) : null,
            ],
          }),
        ],
      }),
    ],
  })
}

// --- Aggregated stats view: model usage bars + tool leaderboard ---
function StatsView({ modelStats, toolStats, errorStats, windowTaskStats, t }) {
  // All range/analytics state is internal to StatsView — no cross-component sync.
  const [statsRange, setStatsRange] = useState('window')
  const [analyticsData, setAnalyticsData] = useState(null)
  const [analyticsLoading, setAnalyticsLoading] = useState(false)
  const [analyticsError, setAnalyticsError] = useState(null)

  // Fetch official analytics when a day-range is selected.
  useEffect(() => {
    if (statsRange === 'window') {
      setAnalyticsData(null)
      setAnalyticsError(null)
      setAnalyticsLoading(false)
      return
    }
    const days = parseInt(statsRange, 10)
    if (!days || days < 1) return
    let cancelled = false
    setAnalyticsLoading(true)
    setAnalyticsError(null)
    ;(async () => {
      try {
        const [modelsRes, usageRes] = await Promise.all([
          window.duckworkDesktop.api({ path: `/api/analytics/models?days=${days}`, timeoutMs: 10000 }),
          window.duckworkDesktop.api({ path: `/api/analytics/usage?days=${days}`, timeoutMs: 10000 }),
        ])
        if (!cancelled) {
          setAnalyticsData({
            period_days: days,
            models: (modelsRes && modelsRes.models) || [],
            tools: (usageRes && usageRes.tools) || [],
            byTask: (usageRes && usageRes.by_task) || [],
            totals: (modelsRes && modelsRes.totals) || (usageRes && usageRes.totals) || {},
          })
        }
      } catch (e) {
        if (!cancelled) setAnalyticsError(String((e && e.message) || e))
      } finally {
        if (!cancelled) setAnalyticsLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [statsRange])

  const RANGES = [
    { key: 'window', label: t.rangeWindow },
    { key: '1', label: t.range1d },
    { key: '3', label: t.range3d },
    { key: '7', label: t.range7d },
    { key: '30', label: t.range30d },
    { key: '90', label: t.range90d },
  ]

  // --- layout helpers (all inline styles — no Tailwind layout dependency) ---
  const ROW = { display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 8px', borderBottom: '1px solid var(--al-fill)' }
  const HDR = { display: 'flex', alignItems: 'center', gap: '8px', padding: '3px 8px', borderBottom: '1px solid var(--al-line-strong)' }
  const nameCell = (w, color) => ({
    width: `${w}px`, minWidth: '0', maxWidth: `${w}px`, flexShrink: 0, overflow: 'hidden',
    fontFamily: 'monospace', fontSize: '12px', color: color || 'var(--al-muted)',
    whiteSpace: 'nowrap', textOverflow: 'ellipsis', display: 'block',
  })
  const numCell = (w, color) => ({
    width: `${w}px`, minWidth: `${w}px`, flexShrink: 0, textAlign: 'right',
    fontFamily: 'monospace', fontSize: '11px', color: color || 'var(--al-muted)',
  })
  const hdrCell = (w, label, title) => jsx('span', { style: { ...numCell(w), fontSize: '10px', opacity: 0.7 }, title, children: label })
  const errorCard = (label, value, color, title) =>
    jsxs('div', {
      title,
      style: {
        flex: '1 1 0', minWidth: '64px', padding: '8px 4px', borderRadius: '6px',
        backgroundColor: 'var(--al-fill-soft)', textAlign: 'center',
      },
      children: [
        jsx('div', { style: { fontSize: '20px', fontWeight: 700, fontFamily: 'monospace', color: value > 0 ? color : 'var(--al-faint)' }, children: `${value}` }),
        jsx('div', { style: { fontSize: '10px', color: 'var(--al-muted)', marginTop: '2px' }, children: label }),
      ],
    })

  // --- click-to-copy for model rows: copies the WHOLE row so it can be pasted
  // into a report — 「模型 · 提供商 · 调用 · 总输入 · 缓存命中 · 输出 · 费用」.
  // The copied text is also used as the row's hover title (preview), and the
  // "已复制" badge is keyed on the ROW (model+provider+index), not the model
  // name: the same model legitimately appears several times (different
  // provider/channel rows), and a name-keyed badge lit all of them at once.
  const [copiedKey, setCopiedKey] = useState(null)
  const copyRow = (key, text) => {
    if (!text) return
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).catch(() => fallbackCopy(text))
      } else {
        fallbackCopy(text)
      }
    } catch {
      fallbackCopy(text)
    }
    setCopiedKey(key)
    setTimeout(() => setCopiedKey((cur) => (cur === key ? null : cur)), 1200)
  }

  // --- range selector bar (always visible) ---
  const rangeBar = jsxs('div', {
    style: { display: 'flex', alignItems: 'center', gap: '4px', padding: '8px 10px', borderBottom: '1px solid var(--al-line)', flexWrap: 'wrap' },
    children: [
      jsx('span', { style: { fontSize: '11px', color: 'var(--al-muted)', marginRight: '4px' }, children: t.statsRange }),
      ...RANGES.map((r) => jsx('button', {
        key: r.key,
        onClick: () => {
          // Clear official data synchronously when switching to live mode —
          // do NOT rely on useEffect for this, it creates a render frame
          // where stale analytics data can show through.
          if (r.key === 'window') {
            setAnalyticsData(null)
            setAnalyticsError(null)
            setAnalyticsLoading(false)
          }
          setStatsRange(r.key)
        },
        style: {
          padding: '3px 8px', borderRadius: '4px', border: 'none', cursor: 'pointer',
          fontSize: '11px', fontFamily: 'monospace',
          backgroundColor: statsRange === r.key ? 'var(--al-blue)' : 'var(--al-fill)',
          color: statsRange === r.key ? 'var(--al-on-accent)' : 'var(--al-secondary)',
        },
        children: r.label,
      })),
    ],
  })

  // --- loading / error states for official API ---
  const isWindow = statsRange === 'window'
  if (analyticsLoading && !isWindow) {
    return jsxs('div', { children: [
      rangeBar,
      jsx('div', { style: { padding: '32px 12px', textAlign: 'center', fontSize: '12px', color: 'var(--al-muted)' }, children: t.statsLoading }),
    ] })
  }
  if (analyticsError && !isWindow) {
    return jsxs('div', { children: [
      rangeBar,
      jsx('div', { style: { padding: '16px 12px', textAlign: 'center', fontSize: '11px', color: 'var(--al-red)', fontFamily: 'monospace', wordBreak: 'break-all' }, children: analyticsError }),
    ] })
  }

  // --- official analytics mode (only when a day-range is actively selected) ---
  if (analyticsData && !isWindow) {
    const byModel = analyticsData.models || []
    const tools = analyticsData.tools || []
    // total input = net input + cache reads (the interface's input_tokens is
    // already net of cache, so we must add cache_read back for the real total).
    const maxTotal = byModel.reduce((mx, m) => Math.max(mx, (m.input_tokens || 0) + (m.cache_read_tokens || 0)), 0)

    const aModelRows = byModel.map((m, i) => {
      const cacheRead = m.cache_read_tokens || 0
      const totalIn = (m.input_tokens || 0) + cacheRead
      const hitRate = totalIn > 0 ? (cacheRead / totalIn) * 100 : 0
      const pct = maxTotal > 0 ? Math.max(2, Math.round((totalIn / maxTotal) * 100)) : 2
      const cost = m.estimated_cost != null ? '$' + Number(m.estimated_cost).toFixed(3) : '—'
      const rowKey = `a:${m.model}::${m.provider || ''}::${i}`
      const isCopied = copiedKey === rowKey
      const copyText = modelCopyText(m.model, m.provider, [
        `${t.statsCalls} ${m.api_calls || 0}`,
        `${t.statsTotalIn} ${fmtK(totalIn)}`,
        `${t.statsCacheHit} ${hitRate.toFixed(2)}%`,
        `${t.statsOut} ${fmtK(m.output_tokens)}`,
        m.estimated_cost != null ? `${t.statsCost} ${cost}` : null,
      ])
      return jsxs('div', {
        // Unique key: the same model name can appear multiple times (different
        // provider/channel), duplicate keys corrupt React's keyed reconciliation
        // and leave stale rows behind when switching back to window mode.
        key: rowKey,
        style: { ...ROW, cursor: 'pointer' },
        onClick: () => copyRow(rowKey, copyText),
        title: copyText,
        children: [
          jsx('span', { style: nameCell(120, 'var(--al-blue)'), children: isCopied ? t.copiedBadge : m.model }),
          jsx('div', {
            style: { flex: '1 1 0', minWidth: '24px', height: '12px', borderRadius: '3px', backgroundColor: 'var(--al-fill)', overflow: 'hidden' },
            children: jsx('div', { style: { width: `${pct}%`, height: '100%', backgroundColor: 'var(--al-blue)', opacity: 0.65 } }),
          }),
          jsx('span', { style: numCell(40), children: `${m.api_calls || 0}` }),
          jsx('span', { style: numCell(56), children: fmtK(totalIn) }),
          jsx('span', { style: numCell(56, hitRate > 0 ? 'var(--al-green)' : undefined), children: `${hitRate.toFixed(2)}%` }),
          jsx('span', { style: numCell(48), children: fmtK(m.output_tokens) }),
          jsx('span', { style: numCell(56, 'var(--al-amber)'), children: cost }),
          jsx('span', { style: numCell(40), children: `${m.sessions || 0}` }),
        ],
      })
    })

    const aToolRows = tools.map((tl) => jsxs('div', {
      key: tl.tool,
      style: ROW,
      children: [
        jsx('span', { style: nameCell(160, 'var(--al-green)'), children: tl.tool }),
        jsx('span', { style: numCell(50), children: `${tl.count}` }),
        jsx('span', { style: numCell(50), children: `${Number(tl.percentage).toFixed(1)}%` }),
      ],
    }))

    // --- usage by task (purpose): main chat vs auxiliary jobs (vision,
    // compression, approval, …). Comes straight from /api/analytics/usage
    // by_task; whole row is click-to-copy like the model rows.
    const byTask = analyticsData.byTask || []
    const taskRows = byTask.map((tk, i) => {
      const label = taskLabel(tk.task, t)
      const models = Array.isArray(tk.models) ? tk.models : []
      const cost = tk.estimated_cost != null ? '$' + Number(tk.estimated_cost).toFixed(3) : '—'
      const modelsText = models.join(', ')
      const rowKey = `t:${tk.task}::${i}`
      const isCopied = copiedKey === rowKey
      const copyText = modelCopyText(label, null, [
        `${t.statsTaskCalls} ${tk.api_calls || 0}`,
        `${t.statsTaskIn} ${fmtK(tk.input_tokens)}`,
        `${t.statsTaskOut} ${fmtK(tk.output_tokens)}`,
        tk.estimated_cost != null ? `${t.statsTaskCost} ${cost}` : null,
        models.length ? `${t.statsTaskModels} ${modelsText}` : null,
      ])
      return jsxs('div', {
        key: rowKey,
        style: { ...ROW, cursor: 'pointer' },
        onClick: () => copyRow(rowKey, copyText),
        title: copyText,
        children: [
          jsx('span', {
            style: { ...nameCell(96, 'var(--al-purple)'), display: 'flex', alignItems: 'center', gap: '4px' },
            children: [
              isCopied
                ? jsx('span', { key: 'chk', style: { color: 'var(--al-green)', fontSize: '11px' }, children: '✓' })
                : jsx('span', { key: 'dot', style: { width: '5px', height: '5px', borderRadius: '50%', backgroundColor: 'var(--al-purple)', flexShrink: 0 } }),
              jsx('span', { key: 'lbl', style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }, children: label }),
            ],
          }),
          jsx('span', { style: numCell(50), children: `${tk.api_calls || 0}` }),
          jsx('span', { style: numCell(64, 'var(--al-blue)'), children: fmtK(tk.input_tokens) }),
          jsx('span', { style: numCell(64, 'var(--al-green)'), children: fmtK(tk.output_tokens) }),
          jsx('span', { style: numCell(60, 'var(--al-amber)'), children: cost }),
          jsx('span', {
            style: { flex: '1 1 0', minWidth: '0', fontFamily: 'monospace', fontSize: '10px', color: 'var(--al-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
            title: modelsText,
            children: modelsText || '—',
          }),
        ],
      })
    })

    const hasAny = byModel.length > 0 || tools.length > 0
    if (!hasAny) {
      return jsxs('div', { children: [
        rangeBar,
        jsx('div', { style: { padding: '32px 12px', textAlign: 'center', fontSize: '12px', color: 'var(--al-muted)' }, children: t.statsNoAnalytics }),
      ] })
    }

    const periodLabel = `${analyticsData.period_days || '?'}d`
    return jsxs('div', {
      style: { overflowY: 'auto', maxHeight: 'min(46vh, 400px)' },
      children: [
        rangeBar,
        jsxs('div', { style: { padding: '10px 10px 4px' }, children: [
          jsx('div', { style: { fontSize: '12px', fontWeight: 600, color: 'var(--al-secondary)', marginBottom: '6px' }, children: t.statsModelTitle }),
          jsxs('div', { style: HDR, children: [
            jsx('span', { style: nameCell(120), children: t.model }),
            jsx('span', { style: { flex: '1 1 0', minWidth: '24px' } }),
            hdrCell(40, t.statsCalls), hdrCell(56, t.statsTotalIn), hdrCell(56, t.statsCacheHit), hdrCell(48, t.statsOut), hdrCell(56, t.statsCost), hdrCell(40, t.statsSessions),
          ] }),
          ...aModelRows,
        ] }),
        jsxs('div', { style: { padding: '14px 10px 8px' }, children: [
          jsx('div', { style: { fontSize: '12px', fontWeight: 600, color: 'var(--al-secondary)', marginBottom: '6px' }, children: t.statsToolTitle }),
          jsxs('div', { style: HDR, children: [
            jsx('span', { style: nameCell(160), children: t.tools }),
            hdrCell(50, t.statsCalls), hdrCell(50, t.statsPct),
          ] }),
          ...aToolRows,
        ] }),
        byTask.length > 0 &&
          jsxs('div', { style: { padding: '14px 10px 8px' }, children: [
            jsx('div', { style: { fontSize: '12px', fontWeight: 600, color: 'var(--al-secondary)', marginBottom: '6px' }, children: t.statsTaskTitle }),
            jsxs('div', { style: HDR, children: [
              jsx('span', { style: nameCell(96), children: '' }),
              hdrCell(50, t.statsTaskCalls), hdrCell(64, t.statsTaskIn), hdrCell(64, t.statsTaskOut), hdrCell(60, t.statsTaskCost),
              jsx('span', { style: { flex: '1 1 0', minWidth: '24px', fontSize: '10px', opacity: 0.7, fontFamily: 'monospace' }, children: t.statsTaskModels }),
            ] }),
            ...taskRows,
          ] }),
        jsx('div', { style: { padding: '8px 12px', fontSize: '10px', color: 'var(--al-muted)', opacity: 0.6, textAlign: 'center', fontFamily: 'monospace' }, children: `${periodLabel} · official /api/analytics/models + usage` }),
      ],
    })
  }

  // --- window mode (log-based, existing logic) ---
  const hasData = modelStats.rows.length > 0 || toolStats.length > 0
  if (!hasData) {
    return jsxs('div', { children: [
      rangeBar,
      jsx('div', { style: { padding: '32px 12px', textAlign: 'center', fontSize: '12px', color: 'var(--al-muted)' }, children: t.statsNoData }),
    ] })
  }

  const modelRows = modelStats.rows.map((m, idx) => {
    // Log `in=` is the TOTAL input (cache hit already included — the `cache=` field's
    // denominator equals `in`). So the total is inTok itself; adding cacheRead
    // again would double-count the cached tokens and halve the hit rate.
    const totalIn = m.inTok || 0
    const hitRate = totalIn > 0 ? ((m.cacheRead || 0) / totalIn) * 100 : 0
    const pct = Math.max(2, Math.round((totalIn / modelStats.maxTok) * 100))
    const avgLat = m.latencyN > 0 ? (m.latencySum / m.latencyN).toFixed(1) : '—'
    const rowKey = `w:${m.model}::${m.provider || ''}::${idx}`
    const isCopied = copiedKey === rowKey
    // Window rows have no cost (the log carries none) — the row's last column,
    // average latency, takes its place so the paste still covers the whole row.
    const copyText = modelCopyText(m.model, m.provider, [
      `${t.statsCalls} ${m.calls}`,
      `${t.statsTotalIn} ${fmtK(totalIn)}`,
      `${t.statsCacheHit} ${hitRate.toFixed(2)}%`,
      `${t.statsOut} ${fmtK(m.outTok)}`,
      `${t.statsAvgLatency} ${avgLat}s`,
    ])
    return jsxs('div', {
      // Window rows get a distinct key namespace (`w:`) and index suffix so the
      // reconciliation from analytics mode can never reuse/match an old node.
      key: rowKey,
      style: { ...ROW, cursor: 'pointer' },
      onClick: () => copyRow(rowKey, copyText),
      title: copyText,
      children: [
        jsx('span', { style: nameCell(110, 'var(--al-blue)'), children: isCopied ? t.copiedBadge : m.model }),
        jsx('div', {
          style: { flex: '1 1 0', minWidth: '24px', height: '12px', borderRadius: '3px', backgroundColor: 'var(--al-fill)', overflow: 'hidden' },
          children: jsx('div', { style: { width: `${pct}%`, height: '100%', backgroundColor: 'var(--al-blue)', opacity: 0.65 } }),
        }),
        jsx('span', { style: numCell(36), children: `${m.calls}` }),
        jsx('span', { style: numCell(48), children: fmtK(totalIn) }),
        jsx('span', { style: numCell(56, hitRate > 0 ? 'var(--al-green)' : undefined), children: `${hitRate.toFixed(2)}%` }),
        jsx('span', { style: numCell(44), children: fmtK(m.outTok) }),
        jsx('span', { style: numCell(48), children: `${avgLat}s` }),
        jsx('span', { style: numCell(36, m.fallbacks > 0 ? 'var(--al-amber)' : undefined), children: m.fallbacks > 0 ? `↩${m.fallbacks}` : '' }),
        jsx('span', { style: numCell(36, m.switches > 0 ? 'var(--al-purple)' : undefined), children: m.switches > 0 ? `⇄${m.switches}` : '' }),
      ],
    })
  })

  const toolRows = toolStats.map((tl) => {
    const rate = tl.calls > 0 ? Math.round((tl.success / tl.calls) * 100) : 0
    const avgSec = tl.calls > 0 ? (tl.secondsSum / tl.calls).toFixed(1) : '—'
    const hasFail = tl.fail > 0
    return jsxs('div', {
      key: tl.tool,
      style: ROW,
      children: [
        jsx('span', { style: nameCell(130, hasFail ? 'var(--al-red)' : 'var(--al-green)'), children: tl.tool }),
        jsx('span', { style: numCell(36), children: `${tl.calls}` }),
        jsx('span', { style: numCell(36, 'var(--al-green)'), children: `${tl.success}` }),
        jsx('span', { style: numCell(36, hasFail ? 'var(--al-red)' : 'var(--al-muted)'), children: `${tl.fail}` }),
        jsx('span', { style: numCell(44), children: `${rate}%` }),
        jsx('span', { style: numCell(48), children: `${avgSec}s` }),
      ],
    })
  })

  return jsxs('div', {
    style: { overflowY: 'auto', maxHeight: 'min(46vh, 400px)' },
    children: [
      rangeBar,
      jsxs('div', { style: { padding: '10px 10px 4px' }, children: [
        jsx('div', { style: { fontSize: '12px', fontWeight: 600, color: 'var(--al-secondary)', marginBottom: '6px' }, children: t.statsModelTitle }),
        jsxs('div', { style: HDR, children: [
          jsx('span', { style: nameCell(110), children: t.model }),
          jsx('span', { style: { flex: '1 1 0', minWidth: '24px' } }),
          hdrCell(36, t.statsCalls), hdrCell(48, t.statsTotalIn), hdrCell(56, t.statsCacheHit), hdrCell(44, t.statsOut), hdrCell(48, t.statsAvgLatency), hdrCell(36, t.statsFallback), hdrCell(36, t.statsSwitch, t.statsSwitchHint),
        ] }),
        ...modelRows,
      ] }),
      jsxs('div', { style: { padding: '14px 10px 8px' }, children: [
        jsx('div', { style: { fontSize: '12px', fontWeight: 600, color: 'var(--al-secondary)', marginBottom: '6px' }, children: t.statsToolTitle }),
        jsxs('div', { style: HDR, children: [
          jsx('span', { style: nameCell(130), children: t.tools }),
          hdrCell(36, t.statsCalls), hdrCell(36, t.statsSuccess), hdrCell(36, t.statsFail), hdrCell(44, t.statsRate), hdrCell(48, t.statsAvgLatency),
        ] }),
        ...toolRows,
      ] }),
      // --- window-mode usage by task (see windowTaskStats in LogPopover) ---
      (() => {
        const rows = Array.isArray(windowTaskStats) ? windowTaskStats : []
        if (rows.length === 0) {
          return jsxs('div', { style: { padding: '14px 10px 8px' }, children: [
            jsx('div', { style: { fontSize: '12px', fontWeight: 600, color: 'var(--al-secondary)', marginBottom: '6px' }, children: t.statsTaskTitle }),
            jsx('div', { style: { fontSize: '11px', color: 'var(--al-muted)', lineHeight: 1.6, padding: '2px 0' }, children: t.statsTaskWindowHint }),
          ] })
        }
        return jsxs('div', { style: { padding: '14px 10px 8px' }, children: [
          jsx('div', { style: { fontSize: '12px', fontWeight: 600, color: 'var(--al-secondary)', marginBottom: '6px' }, children: t.statsTaskTitle }),
          jsxs('div', { style: HDR, children: [
            jsx('span', { style: nameCell(104), children: '' }),
            hdrCell(44, t.statsTaskCalls), hdrCell(56, t.statsTaskIn), hdrCell(56, t.statsTaskOut),
            hdrCell(36, t.statsTaskRetries, t.statsTaskRetriesHint),
            jsx('span', { style: { flex: '1 1 0', minWidth: '24px', fontSize: '10px', opacity: 0.7, fontFamily: 'monospace' }, children: '' }),
          ] }),
          ...rows.map((r, i) => {
            const label = taskLabel(r.task, t)
            const hasVol = (r.inTok || 0) + (r.outTok || 0) > 0
            // Background-review lines carry real per-call counts; plain aux
            // "using" events only give a fire count. Label the column honestly.
            const callsText = hasVol ? `${r.calls || r.events}` : `${r.events}`
            const rowKey = `wt:${r.task}::${i}`
            const isCopied = copiedKey === rowKey
            const copyText = modelCopyText(label, null, [
              `${t.statsTaskCalls} ${callsText}`,
              hasVol ? `${t.statsTaskIn} ${fmtK(r.inTok)}` : null,
              hasVol ? `${t.statsTaskOut} ${fmtK(r.outTok)}` : null,
              r.retries > 0 ? `${t.statsTaskRetries} ${r.retries}` : null,
              !hasVol ? t.statsTaskWindowHint : null,
            ])
            return jsxs('div', {
              key: rowKey,
              style: { ...ROW, cursor: 'pointer' },
              onClick: () => copyRow(rowKey, copyText),
              title: copyText,
              children: [
                jsxs('span', {
                  style: { ...nameCell(104, 'var(--al-cyan)'), display: 'flex', alignItems: 'center', gap: '4px' },
                  children: [
                    isCopied
                      ? jsx('span', { key: 'chk', style: { color: 'var(--al-green)', fontSize: '11px' }, children: '✓' })
                      : jsx('span', { key: 'dot', style: { width: '5px', height: '5px', borderRadius: '50%', backgroundColor: 'var(--al-cyan)', flexShrink: 0 } }),
                    jsx('span', { key: 'lbl', style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }, children: label }),
                  ],
                }),
                jsx('span', { style: numCell(44), children: callsText }),
                jsx('span', { style: numCell(56, 'var(--al-blue)'), children: hasVol ? fmtK(r.inTok) : '—' }),
                jsx('span', { style: numCell(56, 'var(--al-green)'), children: hasVol ? fmtK(r.outTok) : '—' }),
                jsx('span', { style: numCell(36, r.retries > 0 ? 'var(--al-amber)' : undefined), children: r.retries > 0 ? `${r.retries}` : '' }),
                jsx('span', {
                  style: { flex: '1 1 0', minWidth: '0', fontFamily: 'monospace', fontSize: '10px', color: 'var(--al-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
                  children: hasVol ? '' : t.statsTaskWindowHint,
                }),
              ],
            })
          }),
        ] })
      })(),
      jsxs('div', { style: { padding: '14px 10px 8px' }, children: [
        jsx('div', { style: { fontSize: '12px', fontWeight: 600, color: 'var(--al-secondary)', marginBottom: '6px' }, children: t.statsErrorTitle }),
        jsxs('div', { style: { display: 'flex', flexWrap: 'wrap', gap: '6px' }, children: [
          errorCard(t.statsErrLevel, errorStats.error, 'var(--al-red)'),
          errorCard(t.statsWarnLevel, errorStats.warning, 'var(--al-amber)'),
          errorCard(t.statsCallFailed, errorStats.callFailed, 'var(--al-red)'),
          errorCard(t.statsStreamFailed, errorStats.streamError, 'var(--al-red)'),
          errorCard(t.statsToolError, errorStats.toolError, 'var(--al-red)'),
          errorCard(t.statsFallback, errorStats.fallback, 'var(--al-amber)'),
          errorCard(t.statsRetry, errorStats.retry, 'var(--al-amber)'),
          errorCard(t.statsCredExhausted, errorStats.credExhausted, 'var(--al-red)'),
          errorCard(t.statsRateLimited, errorStats.rateLimited, 'var(--al-amber)'),
          errorCard(t.statsCredDegraded, errorStats.credDegraded, 'var(--al-orange)', t.statsCredDegradedHint),
        ] }),
        jsx('div', { style: { fontSize: '10px', color: 'var(--al-muted)', opacity: 0.7, padding: '2px 0 0', fontFamily: 'monospace' }, children: t.statsCardsHint }),
      ] }),
      jsx('div', { style: { padding: '8px 12px', fontSize: '10px', color: 'var(--al-muted)', opacity: 0.6, textAlign: 'center', fontFamily: 'monospace' }, children: t.statsWindowLines(WINDOW_LINES) }),
    ],
  })
}

// Lines added between two fetches of the same tail window. Log lines embed
// their own timestamp, so an exact-string set difference is a faithful count in
// the normal case. Returns null when the old window is gone entirely (log
// rotation, or more arrivals than the window holds) — then "N new" would be a
// misleading number, so the caller shows a plain "refreshed".
function countAddedLines(prev, next) {
  if (!prev || prev.length === 0) return null
  if (prev === next) return 0
  const seen = new Set(prev)
  let added = 0
  for (const line of next) if (!seen.has(line)) added++
  if (added === 0) return 0
  if (added >= prev.length) return null
  return added
}

// --- Floating popover ---
const LogPopover = forwardRef(function LogPopover({ position, onClose, t, model, provider, ctx, lastAlertSeenRef, onAlert }, ref) {
  const [lines, setLines] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [filter, setFilter] = useState('all')
  const [auto, setAuto] = useState(true)
  // Refresh interval — persisted per plugin so the choice survives reloads.
  const [refreshMs, setRefreshMs] = useState(() => {
    try {
      const v = ctx?.storage?.get?.('refreshMs', null)
      return REFRESH_OPTIONS.includes(v) ? v : REFRESH_MS
    } catch { return REFRESH_MS }
  })
  const [updatedAt, setUpdatedAt] = useState(null)
  const [loading, setLoading] = useState(true)
  // Manual-refresh feedback. Without these the button was wired correctly but
  // indistinguishable from a no-op: auto-refresh pulls the same window every few
  // seconds, so the only visible change was a 9px footer timestamp. `refreshing`
  // covers the in-flight request, `fetchStatus` the verdict (new lines / none),
  // and `tickNonce` restarts the interval phase so a click is never "wasted"
  // just before the next scheduled tick.
  const [refreshing, setRefreshing] = useState(false)
  const [fetchStatus, setFetchStatus] = useState(null)
  const [tickNonce, setTickNonce] = useState(0)
  const prevLinesRef = useRef(null)
  const statusTimerRef = useRef(null)

  const fetchLogs = useCallback(async (manual) => {
    if (manual) setRefreshing(true)
    try {
      const res = await host.logs({ file: LOG_FILE, lines: WINDOW_LINES })
      const next = res && Array.isArray(res.lines) ? res.lines : []
      if (manual) {
        // Every log line carries its own timestamp, so a plain set difference
        // counts the arrivals accurately enough for a UI hint. null means the
        // window scrolled past the old one entirely (a full refresh worth of
        // lines), which is not a number worth showing.
        const added = countAddedLines(prevLinesRef.current, next)
        setFetchStatus(
          added === null ? { kind: 'done' } : added === 0 ? { kind: 'none' } : { kind: 'new', n: added }
        )
        if (statusTimerRef.current) clearTimeout(statusTimerRef.current)
        statusTimerRef.current = setTimeout(() => setFetchStatus(null), STATUS_MS)
      }
      prevLinesRef.current = next
      setLines(next)
      setUpdatedAt(new Date())
      setLoadError(null)
    } catch (e) {
      setLoadError(String((e && e.message) || e))
      if (manual) setFetchStatus({ kind: 'error' })
    } finally {
      if (manual) setRefreshing(false)
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchLogs(false)
  }, [fetchLogs])

  useEffect(() => () => { if (statusTimerRef.current) clearTimeout(statusTimerRef.current) }, [])

  const manualRefresh = useCallback(() => {
    if (refreshing) return
    fetchLogs(true)
    setTickNonce((n) => n + 1)
  }, [refreshing, fetchLogs])

  // Auto-refresh only while the popover is open and the toggle is on.
  // `tickNonce` is a dep so a manual click re-arms the timer at its own phase.
  useEffect(() => {
    if (!auto) return
    const id = setInterval(() => fetchLogs(false), refreshMs)
    return () => clearInterval(id)
  }, [auto, fetchLogs, refreshMs, tickNonce])

  const events = useMemo(() => {
    if (!lines || lines.length === 0) return []
    const out = []
    for (let i = lines.length - 1; i >= 0; i--) {
      const ev = parseLogLine(lines[i])
      if (ev) out.push(ev)
    }
    // Fold repeated-state lines (see collapseRepeats) before anything consumes
    // the feed — stats use each row's repeatCount for true occurrence counts.
    return collapseRepeats(out)
  }, [lines])

  // Alert detection: while the popover is open its auto-refresh is the live feed
  // (the chip's own poll is paused), so either side can be the one that spots a
  // new alert. For every ALERT_TYPES class we take the newest occurrence in the
  // feed and hand it to the SHARED bookkeeping (chip-owned) — the chip then goes
  // red for FB_ALERT_MS. events are newest-first, so the first hit per class is
  // the newest one.
  useEffect(() => {
    if (!events || events.length === 0 || !lastAlertSeenRef) return
    const newest = {}
    for (const ev of events) {
      if (ALERT_TYPES.includes(ev.type) && newest[ev.type] == null) {
        newest[ev.type] = evEpoch(ev)
        if (ALERT_TYPES.every((tp) => newest[tp] != null)) break
      }
    }
    const reason = reportAlerts(lastAlertSeenRef.current, newest, Date.now(), ALERT_FRESH_MS)
    if (reason && onAlert) onAlert(reason)
  }, [events])


  const stats = useMemo(() => {
    const s = { calls: 0, tools: 0, errs: 0, errBase: 0, errTool: 0, warns: 0, fallbacks: 0, degraded: 0, inT: 0, outT: 0 }
    for (const ev of events) {
      if (ev.type === 'api_call') {
        s.calls++
        s.inT += ev.inTok || 0
        s.outT += ev.outTok || 0
      } else if (ev.type === 'tool_done') {
        // tools pill counts SUCCESSFUL tool calls only — tool failures belong
        // to the error pill (see the tool_error branch below), not here.
        s.tools++
      } else if (ev.type === 'tool_error') {
        s.errs++
        s.errTool++
      } else if (
        ev.type === 'call_failed' ||
        ev.type === 'stream_error' ||
        ev.type === 'cred_exhausted' ||
        ev.type === 'rate_limited' ||
        ev.level === 'ERROR'
      ) {
        s.errs++
        s.errBase++
      } else if (ev.type === 'cred_degraded') {
        // Persistent provider state, not an incident: counted by TRUE occurrence
        // count on its own card and deliberately kept OUT of the warning pill
        // (it was 44 of 64 warning rows in a 400-line window).
        s.degraded += (ev.repeatCount || 1)
      } else if (ev.level === 'WARNING') {
        s.warns++
      }
      if (ev.type === 'fallback') s.fallbacks++
    }
    return s
  }, [events])

  const visible = useMemo(() => {
    const pred = FILTERS[filter] || FILTERS.all
    return events.filter(pred)
  }, [events, filter])

  const shown = visible.slice(0, MAX_ROWS)
  const counts = useMemo(() => {
    const c = { all: events.length, calls: 0, tools: 0, turns: 0, errors: 0 }
    for (const ev of events) {
      if (FILTERS.calls(ev)) c.calls++
      if (FILTERS.tools(ev)) c.tools++
      if (FILTERS.turns(ev)) c.turns++
      if (FILTERS.errors(ev)) c.errors++
    }
    return c
  }, [events])

  // Aggregated model usage: calls, tokens, avg latency, fallback count per model
  const modelStats = useMemo(() => {
    const map = new Map()
    for (const ev of events) {
      if (ev.type === 'api_call' && ev.model) {
        const m = map.get(ev.model) || { model: ev.model, provider: ev.provider, calls: 0, inTok: 0, outTok: 0, totalTok: 0, cacheRead: 0, latencySum: 0, latencyN: 0, fallbacks: 0, switches: 0 }
        m.calls++
        if (ev.inTok) m.inTok += ev.inTok
        if (ev.outTok) m.outTok += ev.outTok
        if (ev.totalTok) m.totalTok += ev.totalTok
        if (ev.cacheUsed) m.cacheRead += ev.cacheUsed
        if (ev.latency != null) { m.latencySum += ev.latency; m.latencyN++ }
        if (ev.provider && !m.provider) m.provider = ev.provider
        map.set(ev.model, m)
      } else if (ev.type === 'fallback' && ev.to) {
        const m = map.get(ev.to)
        if (m) m.fallbacks++
      } else if (ev.type === 'model_switch' && ev.to) {
        // Manual runtime switch INTO this model (user-initiated, NOT a
        // fallback) — counted separately so it never pollutes the ↩ column.
        const m = map.get(ev.to)
        if (m) m.switches++
      }
    }
    const rows = Array.from(map.values())
    rows.forEach((m) => { m.totalIn = m.inTok || 0 })
    rows.sort((a, b) => b.totalIn - a.totalIn)
    return { rows, maxTok: rows.length ? rows[0].totalIn : 1 }
  }, [events])

  // Aggregated tool usage: calls, success, fail, rate, avg seconds per tool
  const toolStats = useMemo(() => {
    const map = new Map()
    for (const ev of events) {
      if (ev.type !== 'tool_done' && ev.type !== 'tool_error') continue
      const name = ev.tool || '?'
      const m = map.get(name) || { tool: name, calls: 0, success: 0, fail: 0, secondsSum: 0, charsSum: 0 }
      m.calls++
      if (ev.type === 'tool_done') {
        m.success++
        if (ev.chars) m.charsSum += ev.chars
      } else {
        m.fail++
      }
      if (ev.seconds != null) m.secondsSum += ev.seconds
      map.set(name, m)
    }
    const rows = Array.from(map.values())
    rows.sort((a, b) => b.calls - a.calls)
    return rows
  }, [events])

  // Aggregated error/warning/fallback counts for the stats view
  const errorStats = useMemo(() => {
    const s = { error: 0, warning: 0, callFailed: 0, streamError: 0, toolError: 0, fallback: 0, retry: 0, credExhausted: 0, rateLimited: 0, credDegraded: 0 }
    for (const ev of events) {
      if (ev.level === 'ERROR') s.error++
      else if (ev.type === 'cred_degraded') s.credDegraded += (ev.repeatCount || 1)
      else if (ev.level === 'WARNING') s.warning++
      if (ev.type === 'call_failed') s.callFailed++
      else if (ev.type === 'stream_error') s.streamError++
      else if (ev.type === 'tool_error') s.toolError++
      else if (ev.type === 'fallback') s.fallback++
      else if (ev.type === 'retry') s.retry++
      else if (ev.type === 'cred_exhausted') s.credExhausted++
      else if (ev.type === 'rate_limited') s.rateLimited++
    }
    return s
  }, [events])

  // Window-mode task (purpose) rows. Only "Background review complete" lines
  // carry token counts in agent.log; other auxiliary tasks log model selection
  // ("Auxiliary approval: using …") but no tokens, so they are counted as
  // fire events without volume. StatsView renders the rows present and shows a
  // hint pointing at the 1d+ official analytics for the full breakdown.
  const windowTaskStats = useMemo(() => {
    const map = new Map()
    const bump = (key, fn) => {
      const r = map.get(key) || { task: key, events: 0, calls: 0, inTok: 0, outTok: 0, cacheRead: 0, retries: 0 }
      fn(r)
      map.set(key, r)
    }
    for (const ev of events) {
      if (ev.type === 'bg_review') {
        bump('background_review', (r) => {
          r.events++
          r.calls += ev.bgCalls || 0
          r.inTok += ev.inTok || 0
          r.outTok += ev.outTok || 0
          r.cacheRead += ev.bgCacheRead || 0
        })
      } else if (ev.logger === 'agent.auxiliary_client') {
        // "Auxiliary <task>: using <provider> (<model>) at <url>" — one model
        // selection per actual aux call attempt. Retry lines
        // ("transient transport error") count separately — no alert, just a
        // lookup column so a retry storm is discoverable before it gets loud.
        const m = ev.message.match(/^Auxiliary ([a-z_]+): using /)
        if (m) bump(m[1], (r) => { r.events++ })
        else {
          const mr = ev.message.match(/^Auxiliary ([a-z_]+): transient transport error/)
          if (mr) bump(mr[1], (r) => { r.retries = (r.retries || 0) + 1 })
        }
      }
    }
    return Array.from(map.values()).sort((a, b) => b.inTok - a.inTok || b.events - a.events)
  }, [events])

  // Latest actually-called model from the log (events are newest-first).
  // Used in the header so it stays live even when the chip's 30s poll is
  // paused (popover open). Falls back to the model/provider passed in props.
  const liveFromLog = useMemo(() => {
    for (const ev of events) {
      if (ev.type === 'api_call' && ev.model) return { model: ev.model, provider: ev.provider }
    }
    return null
  }, [events])
  const headerModel = liveFromLog?.model || model
  const headerProvider = liveFromLog?.provider || provider

  const tabs = [
    ['all', t.tabAll, counts.all],
    ['calls', t.tabCalls, counts.calls],
    ['tools', t.tabTools, counts.tools],
    ['turns', t.tabTurns, counts.turns],
    ['errors', t.tabErrors, counts.errors],
    ['stats', t.tabStats, ''],
  ]

  // One source of truth for the manual-refresh verdict, shared by the header
  // button and the footer line so the feedback lands wherever the eye happens
  // to be (the timestamp alone was too subtle to notice).
  const statusKind = refreshing ? 'busy' : fetchStatus ? fetchStatus.kind : null
  const statusText =
    statusKind === 'busy' ? t.refreshing
      : statusKind === 'new' ? t.refreshNew(fetchStatus.n)
      : statusKind === 'none' ? t.refreshNoNew
      : statusKind === 'error' ? t.loadError
      : statusKind === 'done' ? t.refreshDone
      : null

  const footer = `${updatedAt ? `${t.updatedAt} ${updatedAt.toLocaleTimeString('zh-CN', { hour12: false })}` : t.loading}${statusText ? ` · ${statusText}` : ''} · ${t.linesSuffix} · ${events.length} ${t.events} · ${t.copyHint}`

  return jsx('div', {
    ref,
    style: {
      position: 'fixed',
      top: `${position.top}px`,
      left: `${position.left}px`,
      width: '620px',
      maxWidth: 'calc(100vw - 16px)',
      zIndex: 99999,
      backgroundColor: 'var(--al-panel)',
      color: 'var(--al-text)',
    },
    className: 'agent-log-scope rounded-lg border border-(--ui-stroke-secondary) shadow-2xl overflow-hidden',
    children: jsx('div', {
      className: 'flex flex-col',
      children: [
        // Header
        jsxs('div', {
          className: 'flex items-center gap-2 p-2.5 border-b border-(--ui-stroke-secondary)',
          children: [
            jsx('span', { className: 'font-semibold text-sm text-foreground flex-shrink-0', children: t.title }),
            (headerProvider || headerModel) &&
              jsxs('span', {
                // flex-1 with no competing spacer: this row claims every pixel
                // between the title and the controls, so a long slug like
                // "glm-5.3-flash-xxxx" stops truncating at ~10 characters. The
                // controls below are flex-shrink-0, so the name gives way
                // before they do, and `title` carries the full text on hover.
                className: 'flex items-center gap-1.5 font-mono text-[10px] min-w-0 flex-1',
                children: [
                  headerProvider &&
                    jsx('span', {
                      className: 'px-1.5 py-px rounded bg-(--chrome-action-hover) text-(--ui-text-secondary) flex-shrink-0',
                      children: headerProvider,
                    }),
                  headerModel &&
                    jsx('span', { className: 'truncate', title: headerModel, children: headerModel }),
                ],
              }),
            jsxs('button', {
              type: 'button',
              onClick: () => setAuto((v) => !v),
              className:
                'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono hover:bg-(--chrome-action-hover) cursor-pointer flex-shrink-0',
              style: auto ? { color: 'var(--al-green)' } : { color: 'var(--al-muted)' },
              children: [
                jsx('span', { children: t.auto }),
                jsx('span', { children: auto ? 'ON' : 'OFF' }),
              ],
            }),
            jsx('button', {
              type: 'button',
              onClick: () => {
                const idx = REFRESH_OPTIONS.indexOf(refreshMs)
                const next = REFRESH_OPTIONS[(idx + 1) % REFRESH_OPTIONS.length]
                setRefreshMs(next)
                try { ctx?.storage?.set?.('refreshMs', next) } catch {}
              },
              title: t.refreshEvery,
              className:
                'px-1.5 py-0.5 rounded text-[10px] font-mono hover:bg-(--chrome-action-hover) cursor-pointer flex-shrink-0',
              style: auto ? { color: 'var(--al-green)' } : { color: 'var(--al-muted)' },
              children: `${Math.round(refreshMs / 1000)}s`,
            }),
            jsx('button', {
              type: 'button',
              onClick: manualRefresh,
              disabled: refreshing,
              title: t.refreshTip,
              className:
                'px-1.5 py-0.5 rounded text-[10px] font-mono hover:bg-(--chrome-action-hover) cursor-pointer flex-shrink-0',
              style: {
                minWidth: '74px',
                textAlign: 'center',
                opacity: statusKind === 'busy' ? 0.6 : 1,
                color:
                  statusKind === 'busy' ? 'var(--al-blue)'
                    : statusKind === 'new' ? 'var(--al-green)'
                    : statusKind === 'error' ? 'var(--al-red)'
                    : statusKind ? 'var(--al-muted)'
                    : 'var(--ui-text-secondary)',
                animation: statusKind === 'busy' ? 'agent-log-pulse 1.2s ease-in-out infinite' : undefined,
              },
              children: [
                jsx('span', {
                  style: {
                    display: 'inline-block',
                    width: '5px',
                    height: '5px',
                    marginRight: '4px',
                    borderRadius: '9999px',
                    verticalAlign: 'middle',
                    backgroundColor:
                      statusKind === 'new' ? 'var(--al-green)'
                        : statusKind === 'busy' ? 'var(--al-blue)'
                        : statusKind === 'error' ? 'var(--al-red)'
                        : statusKind ? 'var(--al-muted)'
                        : 'transparent',
                  },
                }),
                statusText || t.refresh,
              ],
            }),
            jsx('button', {
              type: 'button',
              onClick: () => {
                try {
                  host.navigate('/command-center?section=system')
                } catch {}
              },
              className:
                'px-1.5 py-0.5 rounded text-[10px] font-mono hover:bg-(--chrome-action-hover) cursor-pointer text-(--ui-text-secondary) flex-shrink-0',
              children: t.nativeLogs,
            }),
            jsx('button', {
              type: 'button',
              onClick: onClose,
              'aria-label': t.close,
              className:
                'w-6 h-6 flex-shrink-0 rounded text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground flex items-center justify-center text-lg leading-none cursor-pointer',
              children: '×',
            }),
          ],
        }),
        // Summary strip
        jsxs('div', {
          className: 'flex flex-wrap items-center gap-1.5 px-2.5 py-1.5 border-b border-(--ui-stroke-secondary)',
          children: [
            jsx(StatPill, { label: t.calls, value: `${stats.calls}`, color: 'var(--al-blue)' }),
            jsx(StatPill, { label: t.input, value: fmtK(stats.inT), color: 'var(--al-blue)' }),
            jsx(StatPill, { label: t.output, value: fmtK(stats.outT), color: 'var(--al-green)' }),
            jsx(StatPill, { label: t.tools, value: `${stats.tools}`, color: 'var(--al-green)' }),
            jsx(StatPill, { label: t.fallbacks, value: `${stats.fallbacks}`, color: 'var(--al-amber)' }),
            jsx(StatPill, { label: t.warns, value: `${stats.warns}`, color: 'var(--al-amber)' }),
            jsx(StatPill, { label: t.errors, value: `${stats.errs}`, color: 'var(--al-red)', title: t.errsBreakdown(stats.errBase, stats.errTool, stats.errs) }),
          ],
        }),
        // Filter tabs
        jsxs('div', {
          className: 'flex items-center gap-1 px-2.5 pt-2 pb-1 border-b border-(--ui-stroke-secondary)',
          children: tabs.map(([key, label, count]) =>
            jsx('button', {
              key,
              type: 'button',
              onClick: () => setFilter(key),
              className:
                'inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono cursor-pointer transition-colors ' +
                (filter === key
                  ? 'bg-(--chrome-action-hover) text-foreground'
                  : 'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover)'),
              children: [
                jsx('span', { children: label }),
                jsx('span', { className: 'opacity-50', children: count }),
              ],
            })
          ),
        }),
        // Event list
        loading && !lines
          ? jsx('div', {
              className: 'px-3 py-8 text-center text-xs text-(--ui-text-tertiary)',
              children: t.loading,
            })
          : loadError
            ? jsxs('div', {
                className: 'px-3 py-6 text-center',
                children: [
                  jsx('div', { className: 'text-xs text-[var(--al-red)]', children: `${t.loadError}:` }),
                  jsx('div', { className: 'text-[10px] font-mono text-(--ui-text-tertiary) mt-1 break-all', children: loadError }),
                ],
              })
            : filter === 'stats'
              ? jsx(StatsView, { modelStats, toolStats, errorStats, windowTaskStats, t })
              : shown.length === 0
              ? jsxs('div', {
                  className: 'px-3 py-8 text-center flex flex-col items-center gap-1',
                  children: [
                    jsx('div', {
                      className: 'w-6 h-6 rounded-full border-2 border-dashed border-(--ui-stroke-secondary)',
                    }),
                    jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: t.noData }),
                    jsx('div', { className: 'text-[10px] text-(--ui-text-tertiary) opacity-60', children: t.noDataHint }),
                  ],
                })
              : jsxs('div', {
                  className: 'overflow-y-auto',
                  style: { maxHeight: 'min(46vh, 400px)' },
                  children: [
                    shown.map((ev, idx) => jsx(EventRow, { key: `${ev.date} ${ev.time},${ev.ms}-${idx}`, ev, t })),
                    visible.length > shown.length &&
                      jsx('div', {
                        className: 'px-3 py-2 text-[10px] text-(--ui-text-tertiary) opacity-60 text-center',
                        children: `${visible.length - shown.length} ${t.older}`,
                      }),
                  ],
                }),
        // Footer
        jsx('div', {
          className: 'px-3 py-1.5 border-t border-(--ui-stroke-secondary) text-[9px] font-mono text-(--ui-text-tertiary) opacity-70 flex items-center justify-between gap-2',
          children: [
            jsx('span', { className: 'truncate', children: footer }),
            jsx('span', { className: 'flex-shrink-0', children: `${LOG_FILE}.log` }),
          ],
        }),
      ],
    }),
  })
})

// --- Status-bar chip (bottom bar entry) ---
function AgentLogChip({ ctx }) {
  const locale = getLocale()
  const t = STRINGS[locale] || STRINGS.zh

  const modelString = useValue(host.state.model) || ''
  const profileName = useValue(host.state.profile) || null
  const busy = useValue(host.state.busy) || false

  const [modelInfo, setModelInfo] = useState(null)
  useEffect(() => {
    let cancelled = false
    async function fetchModelInfo() {
      try {
        const bridge = typeof window !== 'undefined' ? window.duckworkDesktop : undefined
        if (!bridge?.api) return
        const info = await bridge.api({
          path: '/api/model/info',
          profile: profileName,
          timeoutMs: 5000,
        })
        if (info && !cancelled) setModelInfo(info)
      } catch (e) {
        console.warn('[agent-log] /api/model/info failed', e)
      }
    }
    fetchModelInfo()
    return () => {
      cancelled = true
    }
  }, [profileName])

  // Popover state (declared before liveCall so the 30s poll can read isOpen)
  const [isOpen, setIsOpen] = useState(false)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  const buttonRef = useRef(null)
  const popoverRef = useRef(null)

  // Alert (shared with the popover): lastAlertSeenRef maps alert class → epoch ms
  // of the newest line already seen by EITHER the chip's 30s poll or the
  // popover's live refresh (whichever is awake). A genuinely newer line of any
  // ALERT_TYPES class takes over the single status dot for FB_ALERT_MS; the class
  // name is carried in the tooltip (alertLabel), since the dot itself cannot say
  // which event it is reporting.
  const lastAlertSeenRef = useRef({})
  const [alertReason, setAlertReason] = useState(null)
  const alertTimerRef = useRef(null)
  const handleAlert = useCallback((reason) => {
    setAlertReason(reason)
    if (alertTimerRef.current) clearTimeout(alertTimerRef.current)
    alertTimerRef.current = setTimeout(() => setAlertReason(null), FB_ALERT_MS)
  }, [])
  useEffect(() => () => { if (alertTimerRef.current) clearTimeout(alertTimerRef.current) }, [])

  // Live "actually called" model: poll the tail of agent.log every 30s and
  // take the most recent API call's model/provider. This makes the chip
  // reflect fallbacks (e.g. deepseek → ark-code-latest) instead of staying on
  // the profile's configured model forever.
  // While the popover is open we pause this poll: the popover already refreshes
  // the log every 4s, and a second concurrent host.logs() call can flash a
  // loading indicator. On close we tick once to catch up.
  // The same pass scans for the newest line of EVERY ALERT_TYPES class and feeds
  // the shared alert (see lastAlertSeenRef above) — so the chip ALSO lights up
  // when the popover is closed and a fallback / credential exhaustion lands.
  const [liveCall, setLiveCall] = useState(null)
  useEffect(() => {
    if (isOpen) return
    let cancelled = false
    const tick = async () => {
      try {
        const res = await host.logs({ file: 'agent', lines: 60 })
        const lines = res?.lines || []
        let call = null
        const newest = {}
        for (let i = lines.length - 1; i >= 0; i--) {
          const ev = parseLogLine(lines[i])
          if (!ev) continue
          if (!call) {
            if (ev.type === 'api_call' && ev.model) {
              call = { model: ev.model, provider: ev.provider || null }
            } else if (ev.type === 'model_switch' && ev.to) {
              // Manual switch (newest of api_call/model_switch wins, since we
              // scan newest-first): the switch line's `to` is the current model
              // even before its first api_call lands.
              call = { model: ev.to, provider: ev.toProvider || null }
            }
          }
          if (ALERT_TYPES.includes(ev.type) && newest[ev.type] == null) newest[ev.type] = evEpoch(ev)
          if (call && ALERT_TYPES.every((tp) => newest[tp] != null)) break
        }
        if (cancelled) return
        setLiveCall(call)
        // Shared bookkeeping decides whether anything is genuinely NEW; an OLD
        // line only sets the baseline (no blink on startup), while a fresh one
        // alerts even on its first sighting.
        const reason = reportAlerts(lastAlertSeenRef.current, newest, Date.now(), ALERT_FRESH_MS)
        if (reason) handleAlert(reason)
      } catch { /* keep last value */ }
    }
    tick()
    const id = setInterval(tick, 30000)
    return () => { cancelled = true; clearInterval(id) }
  }, [isOpen, handleAlert])

  const configuredModel = modelInfo?.model || modelString
  const isFallback = !!(liveCall?.model && configuredModel && liveCall.model !== configuredModel)
  const modelName = liveCall?.model || configuredModel
  // When on the configured model, show the pretty provider name from
  // /api/model/info (e.g. "agentrouter"); when fallen back, show the runtime
  // provider key from the log line (e.g. "custom").
  const provider = isFallback
    ? (liveCall?.provider || modelInfo?.provider || '')
    : (modelInfo?.provider || liveCall?.provider || '')

  const POPOVER_W = 620
  // Estimate ≥ real max height so the popover never covers the trigger; the
  // event list scrolls internally (maxHeight min(46vh, 400px)).
  const POPOVER_H = 560

  const updatePosition = useCallback(() => {
    if (!buttonRef.current) return
    const rect = buttonRef.current.getBoundingClientRect()
    const w = Math.min(POPOVER_W, window.innerWidth - 16)
    const left = Math.max(8, Math.min(window.innerWidth - w - 8, rect.right - w))
    const h = Math.min(POPOVER_H, window.innerHeight - 24)
    let top = rect.top - h - 8
    if (top < 8) top = rect.bottom + 8
    if (top + h > window.innerHeight - 8) top = Math.max(8, window.innerHeight - h - 8)
    setPosition({ top, left })
  }, [])

  const handleClick = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (!isOpen) {
      updatePosition()
      setIsOpen(true)
    } else {
      setIsOpen(false)
    }
  }

  // Close on outside click / escape / scroll (escape listener lives here only)
  useEffect(() => {
    if (!isOpen) return
    function handleClickOutside(e) {
      if (popoverRef.current && popoverRef.current.contains(e.target)) return
      if (e.target.closest && e.target.closest('[data-agent-log-trigger]')) return
      setIsOpen(false)
    }
    function handleEscape(e) {
      if (e.key === 'Escape') setIsOpen(false)
    }
    function handleResize() {
      updatePosition()
    }
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleEscape)
      window.addEventListener('resize', handleResize)
      window.addEventListener('scroll', handleResize, true)
    }, 0)
    return () => {
      clearTimeout(timer)
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
      window.removeEventListener('resize', handleResize)
      window.removeEventListener('scroll', handleResize, true)
    }
  }, [isOpen, updatePosition])

  const shortModel = modelName.length > 22 ? `${modelName.slice(0, 22)}…` : modelName
  // ONE status dot, three states — the fallback alert TAKES IT OVER for 30s
  // instead of adding a second indicator (the chip keeps a fixed layout, and a
  // single dot means one place to look):
  //   red pulse  = a new fallback just landed (highest priority, wins over busy)
  //   green pulse = busy / working
  //   steady grey = idle
  const dotColor = alertReason ? 'var(--al-red)' : (busy ? 'var(--al-green)' : 'var(--al-muted)')
  const dotPulse = !!alertReason || busy
  // The dot can no longer carry its own tooltip, so the chip's tooltip states
  // WHY it is red (which alert class) next to the usual fallback/model hint.
  const chipTip = [
    alertLabel(alertReason, t),
    isFallback ? `${t.chipTip}（← ${configuredModel}）` : t.chipTip,
  ].filter(Boolean).join(' · ')

  return jsxs('div', {
    className: 'agent-log-scope inline-flex h-full items-center relative',
    children: [
      jsx('button', {
        ref: buttonRef,
        type: 'button',
        title: chipTip,
        'data-agent-log-trigger': '1',
        onClick: handleClick,
        className:
          'inline-flex h-full items-center gap-1.5 px-2 transition-all ' +
          'hover:bg-(--chrome-action-hover) rounded cursor-pointer active:scale-95 ' +
          (isOpen ? 'bg-(--chrome-action-hover)' : ''),
        children: [
          jsx('span', {
            className: 'inline-flex items-center gap-1',
            children: [
              jsx(Dot, { color: dotColor, pulse: dotPulse }),
              // subtle list glyph
              jsx('svg', {
                width: 12,
                height: 12,
                viewBox: '0 0 16 16',
                style: { display: 'block', color: 'currentColor' },
                children: [
                  jsx('path', {
                    d: 'M1.5 3h6M1.5 8h6M1.5 13h6M10.5 3l3 5-3 5',
                    fill: 'none',
                    stroke: 'currentColor',
                    strokeWidth: 1.5,
                    strokeLinecap: 'round',
                    strokeLinejoin: 'round',
                  }),
                ],
              }),
            ],
          }),
          shortModel &&
            jsx('span', {
              className: 'font-mono text-[10px] text-(--ui-text-secondary) max-w-[180px] truncate',
              children: shortModel,
            }),
        ],
      }),
      isOpen &&
        jsx(LogPopover, {
          ref: popoverRef,
          position,
          onClose: () => setIsOpen(false),
          t,
          model: modelName,
          provider,
          ctx,
          lastAlertSeenRef,
          onAlert: handleAlert,
        }),
    ],
  })
}

export default {
  id: ID,
  name: 'Agent Log',
  register(ctx) {
    ensurePulseKeyframes()
    ensureThemeCss()
    ctx.register({
      id: 'agent-log-chip',
      area: 'statusBar.right',
      order: 130,
      render: () => jsx(AgentLogChip, { ctx }),
    })
  },
}
