// Copies only the plugin's runtime files into a Duckwork home.
// Usage: node scripts/install.mjs [--duckwork-home PATH]   (default: $DUCKWORK_HOME or ~/.duckwork)
import {cp,mkdir} from 'node:fs/promises';
import path, {resolve} from 'node:path';
import os from 'node:os';
const flag=process.argv.indexOf('--duckwork-home');
const home=flag>0&&process.argv[flag+1]?path.resolve(process.argv[flag+1]):process.env.DUCKWORK_HOME || path.join(os.homedir(),'.duckwork');
const target=path.join(home,'plugins','duckwork-workbench');
await mkdir(target,{recursive:true});
await cp(resolve('dashboard'),resolve(target,'dashboard'),{recursive:true});
for (const file of ['plugin.yaml','__init__.py','workbench_cli.py']) await cp(resolve(file),resolve(target,file));
await cp(resolve('desktop-web'),resolve(target,'desktop-web'),{recursive:true});
console.log(`Installed Workbench to ${target}. Enable it with \`duckwork plugins enable duckwork-workbench\`, then run \`duckwork workbench\`.`);
