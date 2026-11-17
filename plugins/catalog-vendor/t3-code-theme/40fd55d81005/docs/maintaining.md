# Maintaining the theme

The whole plugin is `desktop/plugin.js`, loaded by Duckwork as is. Most of it is a stylesheet that targets Duckwork Desktop's markup: data slots, Tailwind classes and row structure. Duckwork changes them without notice, so most maintenance is catching up after a Duckwork update.

## Test

```sh
pnpm install
pnpm exec playwright install chromium
pnpm test
```

To try a change in the live app, install the plugin once with `duckwork plugins install mariomondev/t3-code-theme`, then copy your working file over it. Duckwork reloads it on the spot:

```sh
cp desktop/plugin.js ~/.duckwork/desktop-plugins/t3-code-theme/plugin.js
```

`duckwork plugins update t3-code-theme` puts the released version back.

## After a Duckwork update

1. Open a chat, a split tab, an empty chat, the sidebar in card style and a confirm dialog, and compare them with the screenshots in the README.
2. See what changed in Duckwork since the last verified commit (in the README):

   ```sh
   git -C ~/.duckwork/duckwork-agent diff <verified-commit> HEAD --stat -- apps/desktop/src/app apps/desktop/src/components/ui
   ```

3. Fix the selectors, add or update a fixture test in `tests/`, run `pnpm test`, and check the live app with the copy above.
4. Update the verified version in the README.

## Rules the plugin keeps

- **Plugin SDK only.** The plugin extends Duckwork through SDK areas: the theme (with its `customCSS`), the model pill label (kept in step with the theme by a component in the composer's top slot that draws nothing), the session row slots and the empty chat slot. Its code never uses `document` or `window`, queries or observes the page, adds listeners or nodes, or reads Duckwork' caches. `tests/sdk-only.cjs` enforces this. If the theme needs something CSS and the SDK cannot do, ask for the slot or hook in an issue on `Fordex/duckwork-agent` instead of patching the page.
- **Scoped.** Every CSS rule starts with `:root[data-duckwork-theme="t3-code-theme"]`, and every contribution renders nothing under another theme.
- **No data of its own.** The sidebar rows read the session list and the connections through the SDK, only while the theme is selected and a row is on screen. The plugin makes no model switches or auth calls.
