# YouTube Dock for Duckwork Desktop

Open **YouTube recommendations and Shorts beside your conversation** with the existing native Browser. No address copying, manual-setup mode or beta switch.

## 1.1.0

The manual-setup experiment from 1.1.0-beta.1 has been removed entirely: no switch, address-copy buttons, clipboard access or preference-controlled opening path. The obsolete plugin-scoped preference is removed on activation when storage is available; even if cleanup fails, its value is never read or used.

**One workflow:** choose Home or Shorts → **Open preview**. Pinning remains your own native **Pin to workspace** menu action. No automatic pinning is performed.

## Install

Requires **Duckwork 0.22.2 or later** and the native Desktop app.

In **Capabilities → Plugins → Install from Git**, use `https://github.com/DuckMind/duckwork`, select the Desktop component, and explicitly select ref `v1.1.0` or the full commit from the release. If the dialog does not offer a ref field, use the CLI:

```sh
duckwork plugins install metamindedu/duckwork-youtube-dock --ref v1.1.0
```

For an immutable deployment, replace the tag with the full release commit SHA. Then **Capabilities → Plugins → Rescan** and enable **YouTube Dock** if needed. The Desktop package remains opt-in. No Python backend or runtime dependencies are needed. Catalog acceptance is separate from source publication.

## Use

1. Click **▶ YouTube** in the titlebar, or select **YouTube** in the command palette.
2. Click **Open preview** under **Recommended videos** or **Shorts**. The native Browser opens the destination immediately; there is no copy/paste setup.
3. If you want it visible while switching chats in the same profile, right-click the Browser tab and choose **Pin to workspace**. If the menu says **Unpin from workspace**, it is already pinned; do not click that item to pin it again.
4. Drag the tab or panel boundary to arrange the split.

English and Korean are included; other locales fall back to English.

## Behavior and limitations

- **Open preview / Hide is a native toggle.** An already-open destination shows Hide, even after navigating inside that page. Clicking Hide hides/closes its preview. Use YouTube's logo within the page to return Home without hiding it.
- Duckwork chooses whether to create or reuse a Browser vessel. The plugin does not guarantee a fresh or exclusive tab on every click. Another URL preview can reuse a pinned Browser; pinning gives visibility, not a reservation or cross-profile persistence.
- The plugin does not inspect or verify pin state, navigation completion, login or playback. No private stores, core-DOM automation, raw webviews or guest scripts are used. No Duckwork core files are patched.
- Native Browser login is reused where available; external-browser cookies are not imported. YouTube account, region, age, sign-in and playback restrictions still apply.
- No dedicated always-on-top PIP, ad blocking, Premium bypass or measured CPU/RAM savings are claimed.
- Disabling the launcher removes its menu and command, not an existing Browser tab. Close that tab yourself to stop playback.
- Host SDK/preview behavior can change with updates. Windows native checks and portable tests do not establish full macOS/Linux player or layout coverage.

## Privacy

- Network: only explicit preview clicks load YouTube and its normal third-party requests in the host Browser.
- No cookie, account, recommendation, watch-history or clipboard reads/writes.
- No persistent feature settings. A migration attempts to remove only the obsolete `manualPinGuide` key through the plugin-scoped SDK; it never reads the old value or writes replacement preferences.
- No agent tools, hooks, middleware, model calls, shell commands, backend, polling, telemetry or self-updater.
- The existing download-control stylesheet stays scoped to this plugin's own rendered preview cards.

## Development and verification

```sh
npm ci --ignore-scripts
npm run check
DUCKWORK_SOURCE_ROOT=/path/to/duckwork-agent npm run check
```

Node is needed only for development tests. React tests use an explicit SDK double; the optional native integration compiles the actual preview-link decoder read-only. Regressions cover old ON/OFF values not changing the one-click UI, cleanup failure tolerance, removal of beta exports/UI/clipboard access, fixed destinations, localization, registration/disposal and decoder behavior. CI runs on Windows and Ubuntu against a pinned Duckwork 0.22.2 decoder checkout. Automated tests are not live guest/playback evidence; release notes state the actual native checks.

`docs/menu.png` is the original 1.0.0 launcher screenshot, not evidence of every current host layout or player state.

## 한국어

베타 스위치·주소 복사·수동 설정 모드를 제거했습니다. **상단 YouTube → 추천 피드 또는 쇼츠 → Open preview**로 바로 엽니다. **Pin to workspace만 직접 클릭**하면 됩니다. 새 탭 생성/기존 탭 재사용은 Duckwork의 기본 동작을 따르며, 매번 독점적인 새 탭을 보장하지는 않습니다. 코어나 다른 탭을 자동 조작하지 않습니다.

## Support and license

Report issues in this repository with Duckwork version, OS and the failing step. Never attach cookies, tokens or credentials. [MIT](LICENSE). Independent community software, not affiliated with YouTube, Google or Fordex.
