# Render a static snapshot

`snapshot/kanban_graph.py` writes the graph as one self-contained HTML file: same layout, same
lineage selection and detail panel, no live updates. Use it without Duckwork Desktop: in CI, on a
remote gateway, or to share a board's state.

It needs only Python 3.11+ and reads the boards read-only.

```sh
cd ~/.duckwork/plugins/kanban-graph
python3 snapshot/kanban_graph.py --board website-relaunch --hide-status done
```

The script prints the output path and counts:

```
/home/you/.duckwork/cache/kanban-graph/website-relaunch.html  boards=1 tasks=6 links=8
```

Open the file in any browser.

## Common variants

| Goal | Flags |
|---|---|
| Every board | (no `--board`) |
| Several boards | `--board a --board b` |
| Only open work | `--hide-status done` |
| Running tasks and their lineage | `--focus-status running` |
| Include archived tasks or boards | `--archived`, `--archived-boards` |
| Choose the file | `--out path/to/graph.html` |
| List board slugs | `--list` |

Full flag list: [reference/snapshot-cli.md](../reference/snapshot-cli.md).

## Another Duckwork home or profile root

The script reads boards from `$DUCKWORK_HOME/kanban/boards/` (default `~/.duckwork`). Point it
elsewhere:

```sh
DUCKWORK_HOME=/srv/duckwork python3 snapshot/kanban_graph.py
```

## Sharing

The file embeds task titles, bodies, results and errors. Share it only with people who may read
the boards.
