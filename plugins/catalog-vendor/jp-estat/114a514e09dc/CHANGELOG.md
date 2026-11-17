# Changelog

Tool Search の既定では本の道具が隠れるため、skill の requires_toolsets を外してモデルの skill 一覧に残す。

## 0.1.4

Duckwork Tool Search lists only the first sentence of a tool description, cut at 60 characters. Those sentences now name Japan e-Stat statistics (population, households, wages, prices, prefectures) instead of starting with "Read-only." The read-only limit is the second sentence. The skill is `japan-statistics` (file `skills/estat-figures/SKILL.md`). Its index line names the same figures, and its first line tells the agent to `tool_search` for the e-Stat tools before `web_search`, then `tool_call`.

## 0.1.3

Tool descriptions are at most 1024 characters: `estat_search_tables` 470, `estat_table_info` 582, `estat_get_data` 447. Which survey to search, and how to name an area or a period, is in the estat-figures skill and the README. Each description still starts by saying the tool is read-only and what it returns. `estat_get_data` still says to report only numbers the call returned, not a remembered or approximate figure.

The same four free models were asked one qualification question on the previous descriptions (995 and 909, then 1258 and 1193) and on these. None of them answered. The chat reported `invalid_params` and did not send the message, including when every description was under 1024 characters. There is no before/after session count.

## 0.1.1

`ESTAT_APP_ID` was read from `os.environ` on each call, including when an unexpected error was scrubbed. One Duckwork process can serve more than one profile, so that read can use another profile's application ID. Each call now reads it with `agent.secret_scope.get_secret`. With more than one profile, each profile needs its own `ESTAT_APP_ID`. An HTTP proxy set in the environment is not used for e-Stat requests, so a machine that can reach the network only through a proxy can no longer reach e-Stat. `requires_duckwork` is now `>=0.21.4` (was `>=0.18`); this version is tested on 0.21.4 and later. Duckwork 0.21.2 and 0.21.3 do not load this version. Duckwork 0.18 through 0.21.1 do not check `requires_duckwork`, so they still load it, but it is not tested there.

関門4: limit 0 は既定の 10 にせず断り、10.0 と全角数字と都道府県の短い名は受ける。表が無いときの文は表IDを載せない。

関門2: 総務省統計局、月次と Tokyo などの地名、調査の英語名を説明に足した。
