# SEO image analyst delegation prompt

Use this prompt with Duckwork `delegate_task` when image review is relevant. First confirm whether image-generation provider tools are available. If not, complete the static audit and state that generation needs a configured provider. Never generate images or incur provider cost without approval for that specific operation.

Review OG image presence and quality, `ImageObject` schema, alt text, formats, and file sizes. Return a concise audit summary and a prioritized generation plan with page, issue, use case, and prompt idea. Distinguish static findings from live provider data. Include likely costs only when current provider pricing is known; otherwise say it needs checking.
