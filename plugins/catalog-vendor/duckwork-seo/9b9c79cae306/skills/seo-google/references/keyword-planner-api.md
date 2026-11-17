# Google Ads Keyword Planner (unavailable)

Google Ads Keyword Planner requires Google OAuth. The Duckwork 0.22.2 catalog
build has no approved Google credential route, so the feature is disabled. The
bundled `keyword_planner.py` reports this limitation and does not read local
credential stores or refresh tokens.

Use another enabled keyword research provider documented in the DataForSEO or
Keywords Everywhere skills. Google Ads support can return only when Duckwork
provides an official Google OAuth broker and the plugin is reviewed against the
catalog secret policy.
