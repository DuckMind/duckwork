---
name: bluesky-posts
description: "Bluesky profile, posts, and follower counts. Before web_search, use tool_search to find the Bluesky tools and tool_call to run them."
---

For this kind of request, use tool_search to find this plugin's tools before web_search, then call them with tool_call. Write tool_search queries in English (for example: "Bluesky posts").

Tools: `profile_get`, `author_feed`, `author_watch`. They read a public Bluesky account. They do not post.
