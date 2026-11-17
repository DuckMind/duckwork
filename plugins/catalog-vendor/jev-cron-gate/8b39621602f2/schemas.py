"""Tool schema for jev_cron_gate."""

JEV_CRON_GATE = {
    "name": "jev_cron_gate",
    "description": (
        "Manage Jev wake gates for agent cron jobs. A gate runs before a cron job and asks TypeSafe Jev "
        "one yes/no question ('would running the agent now do useful work?') over a small state snapshot "
        "(files, changed-since-last-run checks, localhost URLs). If Jev is confident the run is pointless, "
        "Duckwork skips the LLM run entirely. Fail-open: any error wakes the agent. "
        "Actions: setup (write gate config + wrapper script, returns the `duckwork cron edit` command to "
        "attach it), test (dry-run the gate now, no state change), status (skip/wake counts from the log), "
        "remove (delete config + wrapper)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["setup", "test", "status", "remove"]},
            "name": {"type": "string", "description": "Gate name, [a-z0-9_-]+. One gate per cron job."},
            "question": {
                "type": "string",
                "description": (
                    "setup only. A statement Jev scores 0..1, phrased so TRUE means the run is worth doing, "
                    "e.g. 'Given this state, running the agent now would make real new progress rather "
                    "than re-reporting that it is still waiting.'"
                ),
            },
            "sources": {
                "type": "string",
                "description": (
                    "setup only. JSON array of what Jev sees: {\"file\": path, \"tail\": N}, "
                    "{\"changed\": [paths]} (modified since the last wake?), {\"url\": localhost URL}, "
                    "{\"text\": static context}."
                ),
            },
            "skip_below": {"type": "number", "description": "setup only. Skip when P(useful) < this. Default 0.2."},
            "max_consecutive_skips": {"type": "integer", "description": "setup only. Force a wake after this many skips in a row. Default 4."},
            "job_id": {"type": "string", "description": "setup only, optional. Cron job id, used to print the attach command."},
        },
        "required": ["action"],
    },
}
