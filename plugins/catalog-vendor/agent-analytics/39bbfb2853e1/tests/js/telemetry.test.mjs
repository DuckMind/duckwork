import test from 'node:test';
import assert from 'node:assert/strict';

import {
  trackDuckworkPluginCta,
  trackDuckworkPluginFeature,
  trackDuckworkPluginImpression,
  withDuckworkPluginPrefix,
} from '../../src/dashboard/telemetry.mjs';

test('withDuckworkPluginPrefix adds the Duckwork plugin prefix once', () => {
  assert.equal(withDuckworkPluginPrefix('refresh_data'), 'duckwork_plugin_refresh_data');
  assert.equal(withDuckworkPluginPrefix('duckwork_plugin_refresh_data'), 'duckwork_plugin_refresh_data');
  assert.equal(withDuckworkPluginPrefix(''), '');
});

test('Duckwork plugin telemetry uses the host Agent Analytics tracker with prefixed ids', () => {
  const calls = [];
  const originalWindow = globalThis.window;

  globalThis.window = {
    aa: {
      track(event, properties) {
        calls.push({ event, properties });
      },
    },
  };

  trackDuckworkPluginImpression('view_ready', { connected: true });
  trackDuckworkPluginFeature('summary_loaded', { projectCount: 2 });
  trackDuckworkPluginCta('refresh_data', { view: 'ready' });

  globalThis.window = originalWindow;

  assert.deepEqual(calls, [
    {
      event: 'duckwork_plugin_impression',
      properties: {
        surface: 'duckwork_plugin',
        id: 'duckwork_plugin_view_ready',
        connected: true,
      },
    },
    {
      event: 'duckwork_plugin_feature_used',
      properties: {
        surface: 'duckwork_plugin',
        feature: 'duckwork_plugin_summary_loaded',
        projectCount: 2,
      },
    },
    {
      event: 'duckwork_plugin_cta_click',
      properties: {
        surface: 'duckwork_plugin',
        id: 'duckwork_plugin_refresh_data',
        view: 'ready',
      },
    },
  ]);
});
