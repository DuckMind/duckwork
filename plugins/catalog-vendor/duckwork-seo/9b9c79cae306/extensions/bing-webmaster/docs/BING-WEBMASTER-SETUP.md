# Bing Webmaster Tools and IndexNow

The fork retains direct scripts for Bing Webmaster reporting and IndexNow submission. Ask Duckwork to invoke credentialed scripts through the native tool:

```json
{"script":"indexnow_submit.py","args":["--help"]}
```

Store `BING_WEBMASTER_API_KEY` and optional `INDEXNOW_KEY` as secrets in the active Duckwork profile, following the current Microsoft and IndexNow documentation. The parent native tool injects only the secrets needed by the selected script. `INDEXNOW_KEY_LOCATION` is nonsecret runtime configuration; the host key itself must never be passed as a command argument. The former extension installers edited Claude settings and are not supported setup flows here. The `seo-bing` workflow is available only if registered by the plugin and its required configuration is present.

IndexNow requires a host key and a publicly served key file at the advertised key URL. Verify the key setup before submitting URLs. Submission changes public indexing state, so obtain approval for the specific submission. Bing Webmaster data also requires verified site ownership and API access. This fork has not made live Bing calls.
