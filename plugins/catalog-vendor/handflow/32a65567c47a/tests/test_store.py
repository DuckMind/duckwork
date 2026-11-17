"""The plan store: statuses, marks, resolution, persistence."""

from __future__ import annotations

from handflow import store


def test_new_plan_starts_the_first_step(hf_home):
    plan = store.new_plan("ship the thing", ["a", "b", "c"])
    assert plan["status"] == "active"
    assert [s["status"] for s in plan["steps"]] == [store.IN_PROGRESS, store.NOT_STARTED, store.NOT_STARTED]
    assert plan["steps"][0]["notes"] == ["started"]
    assert plan["id"].startswith("plan_")


def test_plan_needs_at_least_one_step(hf_home):
    try:
        store.new_plan("goal", [])
    except ValueError as exc:
        assert "step" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_marks_read_like_a_plan(hf_home):
    plan = store.new_plan("goal", ["one", "two"])
    store.mark_step(plan, 1, store.COMPLETED, "done, 2 files")
    store.mark_step(plan, 2, store.BLOCKED, "waiting on Ritesh")
    text = store.render(plan)
    assert "1. [✓] one" in text
    assert "note: done, 2 files" in text
    assert "2. [!] two" in text
    assert "1/2 complete · 1 blocked" in text


def test_starting_a_step_closes_the_other_in_progress_one(hf_home):
    plan = store.new_plan("goal", ["one", "two"])
    store.mark_step(plan, 2, store.IN_PROGRESS)
    assert plan["steps"][0]["status"] == store.COMPLETED
    assert plan["steps"][1]["status"] == store.IN_PROGRESS
    assert any("auto-completed" in n for n in plan["steps"][0]["notes"])


def test_steps_resolve_by_number_id_and_title(hf_home):
    plan = store.new_plan("goal", ["alpha step", "beta step"])
    assert store.find_step(plan, 2)["title"] == "beta step"
    assert store.find_step(plan, plan["steps"][0]["id"])["title"] == "alpha step"
    assert store.find_step(plan, "beta")["title"] == "beta step"
    assert store.find_step(plan, None)["title"] == "alpha step"  # in-progress wins
    assert store.find_step(plan, 99) is None
    assert store.find_step(plan, "nope") is None


def test_mark_step_rejects_junk(hf_home):
    plan = store.new_plan("goal", ["one"])
    for bad in ("finished", "", "NOT_STARTED "):
        try:
            store.mark_step(plan, 1, bad)
        except ValueError as exc:
            assert "status must be" in str(exc)
        else:  # pragma: no cover
            raise AssertionError(f"expected ValueError for {bad!r}")
    try:
        store.mark_step(plan, 7, store.COMPLETED)
    except ValueError as exc:
        assert "no step matches" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_add_step_inserts_where_asked(hf_home):
    plan = store.new_plan("goal", ["one", "three"])
    store.add_step(plan, "two", position=2)
    assert [s["title"] for s in plan["steps"]] == ["one", "two", "three"]
    store.add_step(plan, "four")
    assert plan["steps"][-1]["title"] == "four"


def test_save_load_and_active_pointer(hf_home):
    plan = store.new_plan("goal", ["one"])
    store.save(plan)
    store.set_active(plan["id"])
    assert store.active_plan_id() == plan["id"]
    again = store.active_plan()
    assert again["goal"] == "goal"
    assert store.plan_path(plan["id"]).is_file()


def test_no_active_pointer_falls_back_to_most_recent(hf_home):
    first = store.new_plan("first", ["one"])
    store.save(first)
    second = store.new_plan("second", ["one"])
    store.save(second)
    assert store.active_plan()["goal"] == "second"


def test_state_root_honours_the_env_override(hf_home):
    assert store.state_root() == hf_home
    assert store.plans_dir() == hf_home / "plans"


def test_plan_ids_are_path_safe(hf_home):
    for bad in ("../../etc/passwd", "a/b", ""):
        try:
            store.plan_path(bad)
        except ValueError:
            continue
        assert "/" not in str(store.plan_path(bad).name)
    assert store.plan_path("plan_1_abcd").name == "plan_1_abcd.json"


def test_reindex_repairs_old_or_junk_payloads(hf_home):
    plan = store.reindex({"goal": "legacy", "steps": [{"title": "only"}, {"status": "weird"}]})
    assert plan["status"] == "active"
    assert plan["steps"][0]["status"] == store.NOT_STARTED
    assert plan["steps"][1]["status"] == store.NOT_STARTED
    assert plan["steps"][0]["id"].startswith("s")
    assert isinstance(plan["steps"][1]["notes"], list)


def test_counts_and_open_work(hf_home):
    plan = store.new_plan("goal", ["a", "b", "c"])
    store.mark_step(plan, 1, store.COMPLETED)
    store.mark_step(plan, 3, store.BLOCKED)
    tally = store.counts(plan)
    assert (tally["done"], tally["total"], tally[store.BLOCKED]) == (1, 3, 1)
    assert [s["title"] for s in store.open_work(plan)] == ["b"]


def test_corrupt_plan_files_are_skipped_not_raised(hf_home):
    plan = store.new_plan("goal", ["one"])
    store.save(plan)
    (store.plans_dir() / "broken.json").write_text("{not json", encoding="utf-8")
    assert [p["id"] for p in store.list_plans()] == [plan["id"]]
    assert store.render(None) == "no plan"
