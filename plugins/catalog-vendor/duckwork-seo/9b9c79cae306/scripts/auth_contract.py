"""Credential allowlist for secrets resolved by the Duckwork plugin host."""

SCRIPT_SECRETS: dict[str, frozenset[str]] = {
    "moz_api.py": frozenset({"MOZ_API_KEY"}),
    "bing_webmaster.py": frozenset({"BING_WEBMASTER_API_KEY"}),
    "keywordseverywhere_api.py": frozenset({"KEYWORDSEVERYWHERE_API_KEY"}),
    "backlinks_auth.py": frozenset({"MOZ_API_KEY", "BING_WEBMASTER_API_KEY", "KEYWORDSEVERYWHERE_API_KEY"}),
    "google_auth.py": frozenset({"GOOGLE_API_KEY"}),
    "pagespeed_check.py": frozenset({"GOOGLE_API_KEY"}),
    "crux_history.py": frozenset({"GOOGLE_API_KEY"}),
    "lcp_subparts.py": frozenset({"GOOGLE_API_KEY"}),
    "lighthouse_agentic.py": frozenset({"GOOGLE_API_KEY"}),
    "youtube_search.py": frozenset({"GOOGLE_API_KEY"}),
    "nlp_analyze.py": frozenset({"GOOGLE_API_KEY"}),
    "matomo_auth.py": frozenset({"MATOMO_API_TOKEN", "MATOMO_TOKEN"}),
    "matomo_report.py": frozenset({"MATOMO_API_TOKEN", "MATOMO_TOKEN"}),
    "dataforseo_merchant.py": frozenset({"DATAFORSEO_USERNAME", "DATAFORSEO_PASSWORD"}),
    "indexnow_submit.py": frozenset({"INDEXNOW_KEY"}),
}

# Profile-scoped, non-secret settings resolved through the same Duckwork route so
# child processes never fall back to the launch shell or a different profile.
SCRIPT_PROFILE_CONFIG: dict[str, frozenset[str]] = {
    "matomo_auth.py": frozenset({"MATOMO_URL", "MATOMO_SITE_ID", "MATOMO_IDSITE", "DUCKWORK_SEO_LOCAL_TARGETS"}),
    "matomo_report.py": frozenset({"MATOMO_URL", "MATOMO_SITE_ID", "MATOMO_IDSITE", "DUCKWORK_SEO_LOCAL_TARGETS"}),
}

EXTENSION_SECRETS: dict[tuple[str, str], frozenset[str]] = {
    ("banana", "generate.py"): frozenset({"GOOGLE_AI_API_KEY"}),
    ("banana", "edit.py"): frozenset({"GOOGLE_AI_API_KEY"}),
    ("banana", "validate_setup.py"): frozenset({"GOOGLE_AI_API_KEY"}),
}


def secrets_for(script: str, extension: str | None = None) -> frozenset[str]:
    if extension is None:
        return SCRIPT_SECRETS.get(script, frozenset())
    return EXTENSION_SECRETS.get((extension, script), frozenset())


def profile_config_for(script: str, extension: str | None = None) -> frozenset[str]:
    if extension is not None:
        return frozenset()
    return SCRIPT_PROFILE_CONFIG.get(script, frozenset())
