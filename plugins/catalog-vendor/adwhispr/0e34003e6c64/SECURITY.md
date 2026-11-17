# Security policy

Please report suspected vulnerabilities privately to [basil@adwhispr.com](mailto:basil@adwhispr.com). Do not open a public issue for a security report.

Include the affected file or behavior, reproduction steps, and any relevant logs with secrets removed. We will acknowledge the report and coordinate remediation and disclosure.

The AdWhispr MCP service uses browser-based OAuth 2.1 (PKCE). Duckwork and the pinned `mcp-remote` bridge store the resulting tokens locally, outside this repository. Ad accounts are connected on each platform's own consent screen, and ChatGPT Ads keys are entered on an AdWhispr page, never in chat. Never commit access tokens, advertising-platform credentials, OAuth client secrets, or customer data here.
