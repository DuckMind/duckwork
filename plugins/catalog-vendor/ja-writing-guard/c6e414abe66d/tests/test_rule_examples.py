"""Every rule catches its own example sentence (tests/rule_examples.py)."""

import pytest

from conftest import load_module
from rule_examples import EXAMPLES

det = load_module("detector")
rules = load_module("rules")


def test_every_rule_has_an_example():
    assert set(EXAMPLES) == {r.id for r in rules.RULES}


@pytest.mark.parametrize("rule_id", sorted(EXAMPLES))
def test_rule_catches_its_example(rule_id):
    report = det.check(EXAMPLES[rule_id] + "\nこの文は、規則が例文に当たるかを確かめるために付けています。", "chat")
    assert rule_id in {f.rule for f in report.findings}, [f.rule for f in report.findings]
