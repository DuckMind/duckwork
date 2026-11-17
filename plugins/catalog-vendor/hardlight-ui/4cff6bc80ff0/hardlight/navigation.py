"""Stateless structural navigation analysis, not a usability certification."""
from collections import deque


LIMITS = {"pages": 300, "tasks": 100, "links_per_page": 1000,
          "links_total": 10000, "id_length": 200, "label_length": 500,
          "max_steps": 1000000}


def _string(value, field, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ValueError(f"{field} must be a nonempty string of at most {maximum} characters without control characters")


def _object(value, required, optional, field):
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise ValueError(f"{field} must be an object with fields {', '.join(sorted(required))}" +
                         (f"; optional: {', '.join(sorted(optional))}" if optional else ""))


def _validate(pages, tasks, home):
    if not isinstance(pages, list) or not 1 <= len(pages) <= LIMITS["pages"]:
        raise ValueError("pages must be a list of 1..300 page objects")
    if not isinstance(tasks, list) or len(tasks) > LIMITS["tasks"]:
        raise ValueError("tasks must be a list of 0..100 task objects")
    ids = set()
    total = 0
    for index, page in enumerate(pages):
        field = f"pages[{index}]"
        _object(page, {"id", "label", "links"}, set(), field)
        _string(page["id"], field + ".id", LIMITS["id_length"])
        _string(page["label"], field + ".label", LIMITS["label_length"])
        if page["id"] in ids:
            raise ValueError(f"duplicate page ID at {field}.id")
        ids.add(page["id"])
        if not isinstance(page["links"], list) or len(page["links"]) > LIMITS["links_per_page"]:
            raise ValueError(f"{field}.links must be a list of 0..1000 links")
        total += len(page["links"])
        if total > LIMITS["links_total"]:
            raise ValueError("graph exceeds 10000 total links")
        for link in page["links"]:
            _object(link, {"to", "label"}, set(), field + ".links[]")
            _string(link["to"], field + ".links[].to", LIMITS["id_length"])
            _string(link["label"], field + ".links[].label", LIMITS["label_length"])
    if home is not None:
        _string(home, "home", LIMITS["id_length"])
        if home not in ids:
            raise ValueError("home must reference a declared page ID")
    for index, task in enumerate(tasks):
        field = f"tasks[{index}]"
        _object(task, {"name", "start", "goal"}, {"max_steps"}, field)
        _string(task["name"], field + ".name", LIMITS["label_length"])
        for key in ("start", "goal"):
            _string(task[key], field + "." + key, LIMITS["id_length"])
            if task[key] not in ids:
                raise ValueError(f"{field}.{key} must reference a declared page ID")
        if "max_steps" in task and (type(task["max_steps"]) is not int or not 0 <= task["max_steps"] <= LIMITS["max_steps"]):
            raise ValueError(f"{field}.max_steps must be an integer in 0..1000000; booleans are not budgets")


def _path(adjacency, start, goal):
    parents = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            path = []
            while node is not None:
                path.append(node)
                node = parents[node]
            return path[::-1]
        for target in adjacency[node]:
            if target not in parents:
                parents[target] = node
                queue.append(target)
    return None


def analyze_navigation(pages, tasks, home=None):
    """Return deterministic paths and structural findings for a declared graph.

    Paths preserve input link order when several shortest paths tie. Steps are
    edges, not pages. An absent task budget is never replaced by a click rule.
    """
    try:
        _validate(pages, tasks, home)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    ids = {page["id"] for page in pages}
    adjacency = {page["id"]: [link["to"] for link in page["links"] if link["to"] in ids] for page in pages}
    home = pages[0]["id"] if home is None else home
    unknown, ambiguous = [], []
    for page in pages:
        labels = {}
        for link in page["links"]:
            if link["to"] not in ids:
                unknown.append({"source": page["id"], **link})
            targets = labels.setdefault(link["label"], [])
            if link["to"] not in targets:
                targets.append(link["to"])
        ambiguous.extend({"source": page["id"], "label": label, "targets": targets}
                         for label, targets in labels.items() if len(targets) > 1)
    reachable = {home}
    queue = deque([home])
    while queue:
        for target in adjacency[queue.popleft()]:
            if target not in reachable:
                reachable.add(target)
                queue.append(target)
    goals = {task["goal"] for task in tasks}
    results = []
    for task in tasks:
        path = _path(adjacency, task["start"], task["goal"])
        steps = len(path) - 1 if path is not None else None
        budget = task.get("max_steps")
        results.append({**task, "path": path, "steps": steps,
                        "reachable": path is not None,
                        "over_budget": steps > budget if steps is not None and budget is not None else None})
    return {"ok": True, "home": home, "tasks": results,
            "unknown_targets": unknown, "ambiguous_labels": ambiguous,
            "unreachable_pages": [p["id"] for p in pages if p["id"] not in reachable],
            "dead_ends": [p["id"] for p in pages if not adjacency[p["id"]] and p["id"] not in goals],
            "coverage": {"page_count": len(pages), "edge_count": sum(len(p["links"]) for p in pages),
                         "known_edge_count": sum(map(len, adjacency.values()))},
            "limitations": ["Structural shortest paths are not usability certification.",
                            "Only declared links are analyzed; browser history, permissions, keyboard behavior and real user tasks are not verified."]}
