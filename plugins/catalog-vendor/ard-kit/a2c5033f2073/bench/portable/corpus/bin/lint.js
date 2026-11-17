#!/usr/bin/env node
// markdown-lint: report style problems in a Markdown document.
// Benchmark fixture: reads the file given as argv[2] and prints a count.
const fs = require("fs");
const file = process.argv[2];
if (!file) {
  console.error("usage: markdown-lint FILE.md");
  process.exit(2);
}
const text = fs.readFileSync(file, "utf8");
const problems = text.split("\n").filter((line) => /\s+$/.test(line)).length;
console.log(problems + " trailing-whitespace problem(s) in " + file);
