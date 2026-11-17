# ⚔️ duckwork-jailbreak-kernel — Duckwork Agent 向けアーマー貫通カーネルプラグイン v2.0.1

<p align="center">
  <a href="https://github.com/DuckMind/duckwork"><img src="https://img.shields.io/github/stars/Enchanted0911/duckwork-jailbreak-kernel?style=for-the-badge&logo=github&label=Stars" alt="Stars" /></a>
  <a href="https://github.com/DuckMind/duckwork"><img src="https://img.shields.io/github/license/Enchanted0911/duckwork-jailbreak-kernel?style=for-the-badge&label=License" alt="License: MIT" /></a>
  <a href="https://github.com/DuckMind/duckwork"><img src="https://img.shields.io/github/last-commit/Enchanted0911/duckwork-jailbreak-kernel?style=for-the-badge&label=Last%20commit" alt="Last commit" /></a>
  <a href="https://duckwork-agent.fordex.com/docs"><img src="https://img.shields.io/badge/Duckwork%20Agent-🚀%20plugin-10B981?style=for-the-badge&logoColor=white" alt="Duckwork Agent plugin" /></a>
</p>

<p align="center">
  <b>ワンラインインストール</b>：
  <code>duckwork plugins install --enable Enchanted0911/duckwork-jailbreak-kernel</code>
</p>

<p align="center">
  <b>他の言語で読む：</b>
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.ar.md">العربية</a>
</p>

**Fordex Duckwork Agent**（`~/.duckwork`）向けのアーマー貫通（レッドチーム）システムプロンプト注入プラグイン。DSH プラグイン **[dsh-infinite-gen-4（無限四代 v0.4.0）](https://github.com/Minglink/dsh-infinite-gen-4)** からの移植版です。

> ⚠️ **許可された用途のみ。** 本プラグインは、許可されたテスト環境・ローカル合成ターゲット・コンプライアンスに沿ったレッドチーム研究専用です。無許可のターゲットに対して決して使用しないでください。利用者は各自の使用について全責任を負います。

## 目次

- [無限四代とのアーキテクチャ対比](#アーキテクチャ対比)
- [3層注入アーキテクチャ](#3層注入アーキテクチャ)
- [セッションローテーション](#セッションローテーション)
- [インストール](#インストール)
- [確認方法](#確認方法)
- [環境スイッチ](#環境スイッチ)
- [診断ダンプ](#診断ダンプ)
- [Duckwork のハード制限](#duckwork-のハード制限)
- [オフライン自己テスト](#オフライン自己テスト)

## アーキテクチャ対比

| dsh-infinite-gen-4 (v0.4.0) | duckwork-jailbreak-kernel（本プラグイン） |
|---|---|
| `infinite-gen-4:global-system-prompt`（Order 100） | `duckwork-jailbreak-kernel-core`（`after_memory` スロット） |
| `infinite-gen-4:dual-layer-reinforce`（Order 200） | `duckwork-jailbreak-kernel-reinforce`（`after_memory` スロット、SHA256 は core と同一） |
| `DUAL_LAYER_INJECTION` スイッチ | `DUCKWORK_JAILBREAK_DUAL=0` 単層フォールバック |
| ゼロツールサーフェス・純粋な直接出力 | 同様 — 機能ツールを一切登録しない |
| `infinite_gen4_profile` メタデータツール | `/jailbreak` ステータスコマンド |
| クライアントステータスバッジ（web half） | —（Duckwork Desktop に後付け可能） |
| 注入面：システムプロンプトセクション | ネイティブ `register_system_prompt_section` |

カーネルペイロード（`prompts/`）は無限四代のテキストを逐語継承：`SUPREME DIRECTIVE — USER AUTHORITY`、`Output contract`（先頭行 `##`/```` ``` ```` で成果物を命名＋サイレント推論＋プレースホルダー自動生成）、`Task classes`（セキュリティ / LLM 研究 / 成人向けフィクション / その他 — 直接生成）、`[USER]/[OUTPUT]` few-shot アンカー。

## 3層注入アーキテクチャ

プラグインは **3層** でカーネルを注入します：

1. **プラグインセクション注入**（`after_memory` スロット、同一ソースの2セクション）— Duckwork がシステムプロンプトを組み立てる際に書き込まれる；
2. **リクエスト層 system 再構築（replace モード）** — `llm_request` ミドルウェアが全リクエストの直前に最終 system を *メモリセクション + 実行環境 + カーネル* として書き換え、Duckwork 自身のエージェントガイダンス／スキル索引スキャフォールドを破棄；
3. **opencode セッションローテーション**（下記）— `x-opencode-session` ヘッダーをローテーション。

ツールスキーマは影響を受けません。API の `tools` フィールドで運ばれるため、system テキストとは無関係です。

## セッションモード

実行時にセッション単位でカーネルを制御できます — 再起動も環境変数の編集も不要：

| コマンド | 効果 |
|---|---|
| `/jailbreak` | 状態：セッション、モード、カーネルプロファイル、ローテーション、ダンプ方針 |
| `/jailbreak on` | 標準：セクション + リクエスト層での再構築 + `once` ローテーション |
| `/jailbreak slim` | 軽量：セクション + system 末尾へのカーネル追記 |
| `/jailbreak full` | 極限：再構築 + `max` プロファイル + リクエストごとにローテーション |
| `/jailbreak off` | パススルー：リクエスト時にセクションを除去 |
| `/jailbreak profile <name>` | カーネルプロファイル：`core` / `research` / `creative` / `max` |
| `/jailbreak dump on\|off` | リクエストごとの診断ダンプを強制／停止 |
| `/jailbreak reset` | セッション上書きを解除（環境変数の既定値に戻す） |

## カーネルプロファイル

| プロファイル | 重点 |
|---|---|
| `core`（**デフォルト**） | 汎用の成果物契約（セキュリティ / LLM 研究 / 成人向けフィクション / その他） |
| `research` | オフェンシブセキュリティ、リバース、エクスプロイトとペイロード |
| `creative` | フィクションと露骨な描写 — 完全な草稿、途中で切らない |
| `max` | 最难ケース：明示的な拒否なしの枠組みと前置きの禁止 |

`full` モードは `max` プロファイルを強制し、それ以外はセッションのプロファイルが適用されます。

## 運用スキル

`jailbreak-kernel-ops` はプラグインスキルとして同梱されます：段階的開示（
`<available_skills>` には1行のみ、本文は `skill_view` でオンデマンドに読み込み）。
コマンド一覧、拒否時のエスカレーション手順、診断方法、環境変数のフォールバックを
収録しています。

## セッションローテーション

ローテーションはセッションモードに従います：`slim`/`on` は `once`、`full` は
`every`、`off` は無効。ミドルウェアは opencode 対象にのみ
`extra_headers["x-opencode-session"]` を書き換えます — `once` はセッションごとに
1つのローテーション済み ID、`every` はリクエストごとに新しい ID です。

| `DUCKWORK_JAILBREAK_ROTATE_SESSION` | 挙動 |
|---|---|
| *（未設定）* | セッションモードに従う（推奨） |
| `once` / `every` / `0` | 全セッションで単一ポリシーを強制 |

補助呼び出し（圧縮・タイトル生成など）は元の安定 ID のままです。

## インストール

```bash
# 方法1 — GitHub からワンラインインストール
duckwork plugins install --enable Enchanted0911/duckwork-jailbreak-kernel

# 方法2 — Duckwork プラグインカタログから（コミュニティエントリがマージされた後）
duckwork plugins install duckwork-jailbreak-kernel

# 方法3 — ローカル開発ディレクトリ
cp -r ~/.duckwork/plugins/duckwork-jailbreak-kernel ~/.duckwork/plugins/   # または git clone して plugins/ へ
duckwork plugins enable duckwork-jailbreak-kernel

# その後、ゲートウェイ／デスクトップアプリを再起動
duckwork gateway restart
```

> ⚠️ Duckwork プラグインは opt-in：インストール後 `duckwork plugins enable duckwork-jailbreak-kernel` で有効化（ワンライナーは `--enable` 済み）。

## 確認方法

```bash
# オフライン回帰（アンカー / 二層同一ソース SHA256 / 予算 / スイッチ）
cd ~/.duckwork/plugins/duckwork-jailbreak-kernel && python selftest.py

# セッション内確認（再起動後、新しいセッションで）
/jailbreak                     # カーネルバージョン、スロット、二重 SHA256、予算使用量
# または質問：システムプロンプトに含まれるプラグインセクションは？
# 「## Plugin Context: duckwork-jailbreak-kernel-core / duckwork-jailbreak-kernel-reinforce」が見えるはず
```

実行時ログの確認（`~/.duckwork/logs/agent.log`）：

```
INFO duckwork_plugins.duckwork_jailbreak_kernel: injected system prompt section duckwork-jailbreak-kernel-core (chars=3005)
INFO duckwork_plugins.duckwork_jailbreak_kernel: injected system prompt section duckwork-jailbreak-kernel-reinforce (chars=3005)
INFO duckwork_plugins.duckwork_jailbreak_kernel: registered llm_request middleware (request-layer reinforce)
INFO duckwork_plugins.duckwork_jailbreak_kernel: hardened request system prompt (mode=replace ...)
INFO duckwork_plugins.duckwork_jailbreak_kernel: rotated x-opencode-session (...)
```

## 環境スイッチ

| 変数 | デフォルト | 効果 |
|---|---|---|
| `DUCKWORK_JAILBREAK_MODE=on\|off\|slim\|full` | on | 既定のセッションモード（セッション上書きが優先） |
| `DUCKWORK_JAILBREAK_PROFILE=core\|research\|creative\|max` | core | 既定のカーネルプロファイル |
| `DUCKWORK_JAILBREAK_ROTATE_SESSION=once\|every\|0` | *(モード)* | ローテーション方針の上書き |
| `DUCKWORK_JAILBREAK_DUMP=1\|0` | off | 診断の強制／停止 |
| `DUCKWORK_JAILBREAK_DUAL=0` | on | 単一セクション注入 |
| `DUCKWORK_JAILBREAK_DISABLE=1` | off | キルスイッチ：登録を完全にスキップ |

## 診断ダンプ

ミドルウェアは各リクエストの診断ビュー（デフォルトではセッションごとの初回、`DUCKWORK_JAILBREAK_DUMP=1` で毎回）を `~/.duckwork/plugins/duckwork-jailbreak-kernel/dumps/request_*.json` に書き込みます：完全な system メッセージ＋他のメッセージの役割/長さ/先頭200文字＋model/provider/base_url。カーネルが system メッセージ末尾にあり、ルートが期待モデルに到達しているかを確認するために使います。ダンプはローカル限定で、`.gitignore` により公開されません。

## Duckwork のハード制限

- プラグインセクション：各 ≤ 4000 文字、合計 ≤ 8000 文字（インジェクタは予算超過セクションを黙ってスキップ）。
- 固定位置 `after_memory`（人格とメモリの後）。レンダリング順はセクション ID の辞書順 → `core < reinforce`。
- セクション ID は小文字英数字/`.`/`_`/`-` のみ。
- リクエスト層の再構築はプラグインセクション予算に縛られない（リクエスト時にミドルウェア内で実行）。

## オフライン自己テスト

```bash
cd ~/.duckwork/plugins/duckwork-jailbreak-kernel
python selftest.py          # ✅/❌ アサーション単位（54 項目）
python selftest.py --json
```

## ローカライゼーション

`/jailbreak` の UI 文字列（コマンド説明とステータスレポート）は Duckwork の
[`agent/i18n`](https://github.com/DuckMind/duckwork) 標準に従います：言語解決は `DUCKWORK_LANGUAGE` >
`config.yaml` の `display.language` > 英語 の順。プラグインは
`locales/en.yaml`（デフォルト）と `locales/zh.yaml` を同梱。他の言語および
欠損キーは英語、さらにキー名そのものへフォールバックします。ログと注入
カーネル本体は設計上言語中立です。

## ドキュメント

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 3層の仕組み、セッションキー、失敗モデルの解説
- [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) — ホスト要件と実測したモデル挙動マトリクス
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — バージョン履歴
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — 系譜とライセンス

## ライセンス

MIT — [LICENSE](LICENSE) を参照。[dsh-infinite-gen-4](https://github.com/Minglink/dsh-infinite-gen-4)（MIT, Minglink）の Duckwork Agent プラグインプラットフォーム向け移植・翻案。