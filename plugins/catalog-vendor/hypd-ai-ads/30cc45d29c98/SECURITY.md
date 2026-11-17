# Security policy

Please report suspected vulnerabilities privately to [contact@hypd.ai](mailto:contact@hypd.ai). Do not open a public issue for a security report.

Include the affected file or behaviour, reproduction steps, and any relevant logs with secrets removed. We will acknowledge the report and coordinate a fix and disclosure.

HYPD uses browser-based OAuth 2.1 with PKCE. Tokens are stored on your machine by the MCP connector (`~/.mcp-auth`) or by Duckwork, outside this repository. Never commit access tokens, OAuth client secrets, ad-platform credentials or customer data here.
