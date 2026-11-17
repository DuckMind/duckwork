import pytest

providers = pytest.importorskip("providers")


@pytest.fixture(scope="module")
def profile():
    import importlib.util
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("openpaths_plugin", root / "__init__.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return providers.get_provider_profile("openpaths")


def test_registered_with_aliases(profile):
    assert profile.name == "openpaths"
    assert providers.get_provider_profile("open-paths") is profile
    assert profile.fallback_models[0] == "auto-medium-task"
    assert profile.env_vars == ("OPENPATHS_API_KEY", "OPENPATHS_BASE_URL")


@pytest.mark.parametrize(
    "model,cfg,expected",
    [
        ("auto", {"enabled": False}, "none"),
        ("auto", {"enabled": True, "effort": "xhigh"}, "high"),
        ("auto", {"enabled": True, "effort": "Medium"}, "medium"),
        ("auto", {"enabled": True, "effort": "bogus"}, None),
        ("auto-think", None, "auto"),
        ("autothink", {}, "auto"),
        ("gpt-5.5", None, None),
    ],
)
def test_reasoning_effort(profile, model, cfg, expected):
    _, top = profile.build_api_kwargs_extras(reasoning_config=cfg, model=model)
    assert top.get("reasoning_effort") == expected
