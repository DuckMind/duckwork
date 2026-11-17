# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""真实端到端验证：PluginLlm（宿主配置的模型）+ 真实 SessionDB + 指定会话。

用法: <your-duckwork-venv>/bin/python scripts/e2e_check.py [session_id]
（不传 session_id 时取最近活跃会话）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from duckwork_state import SessionDB

from duckwork_auto_titler.config import load_config
from duckwork_auto_titler.titler import AutoTitler


class Ctx:
    """最小 ctx：真实 PluginLlm（宿主模型通道，含门控检查）。"""

    def __init__(self):
        from agent.plugin_llm import PluginLlm

        self.llm = PluginLlm(plugin_id="duckwork-auto-titler")


def main():
    db = SessionDB()
    sid = sys.argv[1] if len(sys.argv) > 1 else None
    if not sid:
        row = db._conn.execute(
            "SELECT session_id FROM messages ORDER BY id DESC LIMIT 1"
        ).fetchone()
        sid = row["session_id"]
    print(f"目标会话: {sid}")
    print(f"原标题: {db.get_session_title(sid)!r} 来源: {db.get_session_title_source(sid)!r}")

    cfg = load_config()
    print(f"配置: model={cfg['model']!r} strategy={cfg['strategy']} recent_turns={cfg['recent_turns']}")

    titler = AutoTitler(Ctx(), cfg, db=db)
    result = titler.evaluate(sid, force=True)
    print(f"结果: {result}")
    print(f"新标题: {db.get_session_title(sid)!r} 来源: {db.get_session_title_source(sid)!r}")
    db.close()


if __name__ == "__main__":
    main()
