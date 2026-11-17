import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { createRequire } from 'node:module';

// Runtime plugin stays dependency-free; this is development-only discovery.
export const duckworkHome=process.env.DUCKWORK_HOME || (process.platform==='win32'?path.join(process.env.LOCALAPPDATA||path.join(os.homedir(),'AppData','Local'),'duckwork'):path.join(os.homedir(),'.duckwork'));
export const duckworkSource=process.env.DUCKWORK_SOURCE || path.join(duckworkHome,'duckwork-agent');
export const dependencyRoot=process.env.DUCKWORK_NODE_MODULES ? path.resolve(process.env.DUCKWORK_NODE_MODULES,'..') : process.env.DUCKWORK_SOURCE || path.resolve(import.meta.dirname,'..');
if(!fs.existsSync(path.join(dependencyRoot,'package.json')))throw Error('Set DUCKWORK_SOURCE to the Duckwork checkout containing React development dependencies, or DUCKWORK_NODE_MODULES to its node_modules directory.');
export const requireDuckwork=createRequire(path.join(dependencyRoot,'package.json'));
