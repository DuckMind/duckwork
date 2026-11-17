import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import vm from "node:vm";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(readFileSync(path.join(root, "dashboard/manifest.json"), "utf8"));
const version = readFileSync(path.join(root, "plugin.yaml"), "utf8").match(/^version:\s*([\d.]+)/m)[1];
assert.equal(manifest.name, "duckwork-workflows");
assert.equal(manifest.version, version);
assert.equal(manifest.api, "plugin_api.py");
assert.equal(manifest.tab.hidden, true);
assert.equal(typeof manifest.entry, "string");
assert.ok(!manifest.entry.startsWith("/") && !manifest.entry.includes(".."));
console.log("PASS named/versioned hidden API manifest declares a local web entry");

const components = new Map();
const context = vm.createContext({ window: { __DUCKWORK_PLUGINS__: {
  register(name, component) { components.set(name, component); },
} } });
vm.runInContext(readFileSync(path.join(root, "dashboard", manifest.entry), "utf8"), context);
assert.equal(typeof components.get(manifest.name), "function");
assert.equal(components.get(manifest.name)(), null);
assert.equal(components.size, 1);
console.log("PASS web entry registers a null-rendering component (no NO_REGISTER)");
console.log("ALL PASS");
