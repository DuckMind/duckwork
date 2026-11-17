import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

async function readJson(filename) {
  return JSON.parse(await readFile(path.join(root, filename), 'utf8'));
}

test('declares the Titanos portable plugin manifest', async () => {
  const manifest = await readJson('plugin.json');

  assert.equal(manifest.$schema, 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json');
  assert.equal(manifest.name, 'titanos-mcp');
  assert.equal(manifest.version, '0.3.0');
});

test('starts the pinned Titanos MCP package through OAuth even when Duckwork has a legacy key', async () => {
  const mcp = await readJson('mcp.json');
  const server = mcp.mcpServers['titanos-agents'];

  assert.equal(mcp.$schema, 'https://agent-plugins.org/schemas/1.0.0/mcp.schema.json');
  assert.deepEqual(server, {
    type: 'stdio',
    command: 'npx',
    args: ['-y', '@titanos/mcp-agents@1.47.2'],
    env: {
      TITANOS_API_KEY: '',
    },
  });
  assert.doesNotMatch(JSON.stringify(mcp), /tnk_|mcpat_/i);
});

test('ships the Titanos operating skills with the plugin', async () => {
  const skillNames = [
    'titanos-amazon-ads',
    'titanos-listings',
    'titanos-marketplace-operations',
    'titanos-miner',
    'titanos-safe-writes',
    'titanos-seller-operations',
  ];

  for (const skillName of skillNames) {
    const content = await readFile(path.join(root, 'skills', skillName, 'SKILL.md'), 'utf8');
    assert.match(content, new RegExp(`^---\\nname: ${skillName}\\n`, 'm'));
    assert.match(content, /^description: Use when /m);
    assert.match(content, /Titanos/i);
  }
});

test('ships efficient Titanos routing guidance', async () => {
  const skillFiles = [
    'skills/titanos-mcp/SKILL.md',
    'skills/titanos-miner/SKILL.md',
    'skills/titanos-listings/SKILL.md',
    'skills/titanos-marketplace-operations/SKILL.md',
  ];
  const contents = await Promise.all(
    skillFiles.map((filename) => readFile(path.join(root, filename), 'utf8')),
  );
  const base = contents[0];
  const joined = contents.join('\n');

  assert.match(base, /2 chamadas MCP/i);
  assert.match(base, /reutilize.*schema/i);
  assert.doesNotMatch(joined, /discover and describe|descubra e descreva|call `titanos_list_tool_domains`/i);
});

test('ships OAuth installation guidance', async () => {
  const [readme, skill] = await Promise.all([
    readFile(path.join(root, 'README.md'), 'utf8'),
    readFile(path.join(root, 'skills/titanos-mcp/SKILL.md'), 'utf8'),
  ]);

  assert.match(readme, /@titanos\/mcp-agents@1\.47\.2 login/);
  assert.match(skill, /OAuth/i);
  assert.match(readme, /empty `TITANOS_API_KEY` value/);
  assert.doesNotMatch(`${readme}\n${skill}`, /tnk_live_|mcpat_/i);
});
