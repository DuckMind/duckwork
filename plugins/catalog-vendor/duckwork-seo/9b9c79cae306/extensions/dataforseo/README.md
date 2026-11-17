# DataForSEO extension

The fork retains DataForSEO workflow material and cost-ledger utilities. It does not install an MCP package or edit Claude Code settings. Configure a compatible DataForSEO MCP server in Duckwork using the provider's current documentation. Store `DATAFORSEO_USERNAME` and `DATAFORSEO_PASSWORD` as active-profile secrets; the parent native tool injects them only into the selected DataForSEO script.

Use Duckwork `skills_list` and `skill_view` to confirm the DataForSEO workflow is registered. Its source tool catalog covers SERP, keyword, backlink, on-page, competitor, content, business-listing, and AI-visibility data; actual tools depend on the configured server. The bundled cost ledger, where allowlisted, runs through:

```bash
duckwork seo run dataforseo_costs.py --help
```

DataForSEO calls can incur charges. Check current endpoint pricing and obtain approval before paid operations. Local plugin checks do not validate provider connectivity or account access. See [setup notes](docs/DATAFORSEO-SETUP.md) and the provider's [API documentation](https://docs.dataforseo.com/) for current details.
