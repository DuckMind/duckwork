---
description: Index a directory of scripts into an ARD catalog (ai-catalog.json)
argument-hint: <directory> [host]
---

Catalogize the directory given as `$ARGUMENTS` (first token = directory,
optional second token = host, default `myhost.example.com`) into the ARD
catalog:

1. Run: `ard-catalogize --dir <dir> --host <host> --output ai-catalog.json`
   (from the plugin: `python3 -m ard_kit.catalogize` with the same arguments).
2. If an `ard-registry` process or systemd unit is serving this catalog,
   restart it so the new entries are live.
3. Verify with one live search against `/search` and report the entry count.

Follow the ard-registry skill contract; never invent URNs without a live
search.
