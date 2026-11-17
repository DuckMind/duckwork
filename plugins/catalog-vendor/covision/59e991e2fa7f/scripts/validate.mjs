import { readFile } from 'node:fs/promises';

const plugin = JSON.parse(await readFile(new URL('../plugin.json', import.meta.url)));
const mcp = JSON.parse(await readFile(new URL('../mcp.json', import.meta.url)));
const expectedPluginSchema = 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json';
const expectedMcpSchema = 'https://agent-plugins.org/schemas/1.0.0/mcp.schema.json';

if (plugin.$schema !== expectedPluginSchema || !plugin.name || !plugin.version) {
  throw new Error('plugin.json is not a complete Agent Plugins v1 manifest');
}
if (mcp.$schema !== expectedMcpSchema || !mcp.mcpServers || Object.keys(mcp).some((key) => !['$schema', 'mcpServers'].includes(key))) {
  throw new Error('mcp.json is not a valid Agent Plugins v1 MCP manifest');
}
const covision = mcp.mcpServers.covision;
if (!covision || covision.type !== 'streamable-http' || covision.url !== 'https://connector.covisionperformance.com/mcp') {
  throw new Error('Covision MCP endpoint declaration is invalid');
}
console.log('Covision Agent Plugin manifests are valid.');
