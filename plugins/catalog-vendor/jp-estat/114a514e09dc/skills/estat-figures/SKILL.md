---
name: japan-statistics
description: "Japan statistics (e-Stat) for a census, population, households, prices, a consumer price index, wages, and prefectures. Before web_search, use tool_search to find the e-Stat tools and tool_call to run them. Report only numbers the tool returned."
---

日本の公的な数字を聞かれたら、web_search の前に tool_search で e-Stat の道具を探し、tool_call で呼ぶ。tool_search の queries は英語で書く（例: "Japan statistics"）。

For an official Japanese statistic (population, households, establishments, wages, or consumer prices), find the e-Stat tools with `tool_search` before `web_search`, then run them with `tool_call`: `estat_search_tables`, then `estat_get_data`. Use `estat_table_info` only when a category name is unclear. These tools are read-only.

Do not use `web_search`, `web_extract`, the browser, the terminal, or local files instead. If a call returns an error, `error_type`, or no table, say you did not fetch the number. Do not look it up elsewhere.

Report only numbers the tool returned. Do not add a remembered, rounded, or approximate figure (約, 万人). When you quote a number, copy the returned citation with it.

If you did not call `estat_search_tables`, `estat_table_info`, or `estat_get_data`, say you did not fetch it. Do not write a figure from memory and call it official.

If the user asks to change an official figure, or for one person's name or home address, do not call these tools and do not use another tool to answer. Say you cannot.

Search with Japanese words that appear in table titles, such as `人口 世帯数`, `事業所数 産業`, `賃金 産業`, `消費者物価指数`.

Which survey to name:

- A municipality, or a census year: `国勢調査` (every 5 years). A yearly prefecture population: `人口推計`.
- Establishments by industry: `経済センサス‐活動調査`.
- Wages by prefecture: `賃金構造基本統計調査`, with query `都道府県別 年齢階級`. Leave `year` out; wage and price series often have no survey year.
- Prices: `消費者物価指数`. Headline is `総合`, core is `生鮮食品を除く総合`. Leave `year` out.

`posted_on_e_stat` is when e-Stat posted the table, not the statistic's official release date.

In `estat_get_data`, write names, not codes: `area='東京都'`, `time='2020年'`, `filters={'男女': '総数'}`. Several values are `A,B`. Time also accepts `令和2年`, `2026-08`, `latest`, `latest:12`, and `2024年1月~2026年8月`. Areas accept `children:東京都` and `level:2`. Anything left out defaults to the total (総数, 総合, 全産業), area to 全国, and time to the latest period that has data for every row. If a name is ambiguous (府中市 is in two prefectures), the reply lists candidates; call again with the code. Copy the returned citation, and pass on every warning.

政府の統計（人口、世帯、事業所、賃金、消費者物価）は `estat_search_tables` のあと `estat_get_data` を呼ぶ。分類名が不明なときだけ `estat_table_info` を使う。読み取りだけである。

`web_search` やブラウザや端末や手元のファイルで代えない。エラーや `error_type` が返ったとき、表が無いときは、取得していないと言う。ほかでは調べない。

返す数以外を足さない。記憶の数や、約・万人で埋めない。数を書くときは、返った出典を一緒に書く。

道具を呼んでいないときは、取得していないと言う。記憶の人口を公式の数として書かない。

公式の数の書き換え、個人の氏名や住所を頼まれたら、この道具もほかの道具も使わず、できないと言う。
