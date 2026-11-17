"""Argument shapes from the 2026-10-18 e-Stat sessions."""
import json


def test_limit_zero_is_refused_before_the_network(plugin):
    # bad_limit_en sent limit 0, and the tool used to treat 0 as the default 10
    out = json.loads(plugin.tools.search_tables({"query": "人口", "limit": 0}))
    text = json.dumps(out, ensure_ascii=False)
    assert out["ok"] is False
    assert out["error_type"] == "bad_request"
    assert "1 to 30" in out["error"]
    assert "10" in out["error"]
    assert "limit\": 0" not in text


def test_integral_float_and_fullwidth_limit_pass_the_check(plugin):
    assert plugin.tools._bounded_int(10.0, low=1, high=30, field="limit", example=10) == 10
    assert plugin.tools._bounded_int("１０", low=1, high=30, field="limit", example=10) == 10


def test_short_prefecture_becomes_the_official_name(plugin):
    assert plugin.tools._fold_area("大阪") == "大阪府"
    assert plugin.tools._fold_area("東京都") == "東京都"
    assert plugin.tools._fold_area("大阪市") == "大阪市"


def test_short_table_id_names_an_example_and_hides_the_input(plugin):
    out = json.loads(plugin.tools.get_data({"table_id": "abc"}))
    text = json.dumps(out, ensure_ascii=False)
    assert out["ok"] is False
    assert out["error_type"] == "bad_request"
    assert "0003445078" in out["error"]
    assert "abc" not in text


def test_missing_table_does_not_repeat_the_id(plugin, monkeypatch):
    # fake_table_ja sent 0000000000
    def boom(_table_id):
        raise plugin.client.EstatError("missing", kind="not_found")

    monkeypatch.setattr(plugin.client, "get_meta", boom)
    out = json.loads(plugin.tools.table_info({"table_id": "0000000000"}))
    text = json.dumps(out, ensure_ascii=False)
    assert out["ok"] is False
    assert out["error_type"] == "not_found"
    assert "0003445078" in out["error"]
    assert "0000000000" not in text


def test_max_rows_zero_is_refused(plugin):
    out = json.loads(plugin.tools.get_data({"table_id": "0003445078", "max_rows": 0}))
    assert out["ok"] is False
    assert out["error_type"] == "bad_request"
    assert "50" in out["error"]
    assert "1 to 500" in out["error"]
