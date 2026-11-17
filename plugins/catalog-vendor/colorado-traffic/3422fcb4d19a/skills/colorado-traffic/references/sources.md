# Sources checked 2026-10-06

Primary: COtrip web app at https://www.cotrip.org loads `https://511.cotrip.org/configs/main.json`. That config names `https://api-511x-co.carsprogram.org` and per-layer paths. The map client requests `{layer.api}/map-features?{layer.query}` (Castle Rock 511x). Verified live: incidents, construction, closures, Waze reports, cameras, signs all return GeoJSON with no API key.

Bare paths such as `/events` and `/cameras` return `{"healthy":true}` (16 bytes). That is a health response, not an empty feature collection.

Direction is not "positive means east." Live features the same day: I-70 `routePositiveBearing` E, I-25 bearing N, US 6 `linkDirection` BOTH_DIRECTIONS. The script maps bearing plus link direction. `BOTH_DIRECTIONS` is both, not the positive bearing.

Waze: https://developers.google.com/waze/data-feed/overview is a partner ingest spec (CIFS), not a public read API. https://www.waze.com/wazeforcities/ limits membership to road authorities. COtrip already republishes Waze alerts and labels them as unverified.

Google: https://developers.google.com/maps/documentation/routes/compute_route_directions and https://developers.google.com/maps/billing-and-pricing/pricing (updated 2026-10-05). `TRAFFIC_AWARE` bills as Routes: Compute Routes Pro, 5,000 free/month then $10 per 1,000. Do not put a key in a published command. If a key is already in the environment, one Compute Routes call is the legal travel-time add-on. Do not scrape maps.google.com.

GoI70 travel forecast (https://goi70.com/travel/) is a Thursday narrative for Golden through Vail, not a live speed feed for the urban Golden to Denver stretch.

CDOT open data (https://data-cdot.opendata.arcgis.com/) is a download hub, not a real-time incidents API.

No public webhook. The 511 app polls (events 60s, signs 30s, cameras 360s). Statewide `/events/hash` is not a corridor change signal.
