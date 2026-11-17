# Google API access in the catalog build

The catalog build supports Google APIs that accept a static API key:
PageSpeed Insights, CrUX, CrUX History, YouTube Data API, and the enabled
Knowledge Graph/Web Risk features. Add `GOOGLE_API_KEY` to the active Duckwork
profile's secret source. The native `duckwork_seo_run` tool resolves it through
Duckwork `agent.secret_scope.get_secret()` and passes it only to the selected
bundled script. Never put credentials in tool arguments, files, shell history,
or global environment variables.

Google Search Console, GA4, Google Ads Keyword Planner, and Indexing API need
Google OAuth or service-account credentials. Duckwork 0.22.2 has no approved
Google credential broker, so those flows are disabled in this catalog build.
Their scripts fail closed and do not read local token/config stores, Google
ADC, service-account files, browser logins, or refresh tokens. Do not configure
Google OAuth credentials for this plugin.

Non-secret property identifiers can be passed as ordinary script arguments
where supported. A static API key does not grant access to private GSC, GA4,
or Ads data.
