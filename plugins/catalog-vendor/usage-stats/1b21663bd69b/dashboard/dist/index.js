(function () {
  "use strict";
  const registry = window.__DUCKWORK_PLUGINS__;
  const SDK = window.__DUCKWORK_PLUGIN_SDK__;
  if (!registry || !SDK) return;

  function HiddenBackendPlugin() {
    return null;
  }

  registry.register("usage-stats", HiddenBackendPlugin);
})();
