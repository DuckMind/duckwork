const PLUGIN_SURFACE = 'duckwork_plugin';
const PLUGIN_PREFIX = 'duckwork_plugin_';

function getTracker() {
  if (typeof window === 'undefined') return null;
  return typeof window.aa?.track === 'function' ? window.aa.track : null;
}

export function withDuckworkPluginPrefix(value) {
  const stringValue = String(value || '').trim();
  if (!stringValue) return '';
  return stringValue.startsWith(PLUGIN_PREFIX) ? stringValue : `${PLUGIN_PREFIX}${stringValue}`;
}

function track(event, properties = {}) {
  const tracker = getTracker();
  if (!tracker) return;
  tracker(event, {
    surface: PLUGIN_SURFACE,
    ...properties,
  });
}

export function trackDuckworkPluginImpression(id, properties = {}) {
  track('duckwork_plugin_impression', {
    id: withDuckworkPluginPrefix(id),
    ...properties,
  });
}

export function trackDuckworkPluginFeature(feature, properties = {}) {
  track('duckwork_plugin_feature_used', {
    feature: withDuckworkPluginPrefix(feature),
    ...properties,
  });
}

export function trackDuckworkPluginCta(id, properties = {}) {
  track('duckwork_plugin_cta_click', {
    id: withDuckworkPluginPrefix(id),
    ...properties,
  });
}
