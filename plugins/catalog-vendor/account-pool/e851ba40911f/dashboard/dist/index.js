(function () {
  "use strict";
  // account-pool: the page lives in Duckwork Desktop (Accounts in the sidebar). This file only
  // registers the plugin so the browser dashboard does not report it as broken; its tab is hidden.
  var plugins = window.__DUCKWORK_PLUGINS__;
  var SDK = window.__DUCKWORK_PLUGIN_SDK__;
  if (!plugins || !SDK) return;
  plugins.register("account-pool", function AccountPool() {
    return SDK.React.createElement("p", { style: { padding: 16 } },
      "Open Duckwork Desktop and choose Accounts in the sidebar, or run: duckwork account anthropic usage");
  });
})();
