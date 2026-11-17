#!/usr/bin/env node
// archive-pack: list the files that would go into an archive.
// Benchmark fixture: echoes the paths given on the command line, one per line.
const files = process.argv.slice(2);
if (files.length === 0) {
  console.error("usage: archive-pack FILE [FILE ...]");
  process.exit(2);
}
for (const file of files) {
  console.log(file);
}
