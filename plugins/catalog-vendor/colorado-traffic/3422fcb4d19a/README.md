# colorado-traffic

Live Colorado highway events for Duckwork Agent, from CDOT's public COtrip 511 API. No API key. No scraping.

## What it does

- Queries incidents, closures, construction, and Waze reports CDOT already ingests
- Default corridor is I-70 mile points 259-279: C-470 at Golden through Quebec Street in east Denver
- Splits each event into **now**, **upcoming**, or **ended**. CDOT's `active` flag is true for future night work. The script trusts the schedule, not the flag.
- Labels Waze reports as "Waze via COtrip", not as CDOT-confirmed incidents
- Maps direction from `routePositiveBearing`. Positive is eastbound on I-70 and northbound on I-25.

It does not publish speeds. COtrip's website draws Google traffic tiles. This plugin does not.

## Install

```bash
git clone https://github.com/drkpxl/colorado-traffic.git
cp -r colorado-traffic/skills/colorado-traffic ~/.duckwork/skills/
```

After the catalog listing is merged, `duckwork plugins install colorado-traffic` is the other path. Until then, copy the skill directory.

Then ask about I-70, COtrip, or a Colorado highway corridor.

### Requirements

- Python 3.10+
- Network access to `https://api-511x-co.carsprogram.org`
- No API key, no account

## Use

```bash
# Inside Duckwork, the skill loader expands ${DUCKWORK_SKILL_DIR} to the
# installed skill directory (catalog-plugin and copied-skill installs alike):
python3 "${DUCKWORK_SKILL_DIR}/scripts/cotrip_corridor.py"

# Plain shell, no Duckwork loader: use the concrete path for your install type.
# Copied-skill install (~/.duckwork/skills/):
python3 ~/.duckwork/skills/colorado-traffic/scripts/cotrip_corridor.py
# Catalog-plugin install (~/.duckwork/plugins/):
python3 ~/.duckwork/plugins/colorado-traffic/skills/colorado-traffic/scripts/cotrip_corridor.py

python3 "${DUCKWORK_SKILL_DIR}/scripts/cotrip_corridor.py" --corridor i70-golden-i25
python3 "${DUCKWORK_SKILL_DIR}/scripts/cotrip_corridor.py" --route "I-25" --min-mp 210 --max-mp 216
```

Done when stdout is JSON with `queried_at`, `counts`, and `layers`.

## Tests

```bash
python3 -m unittest tests/test_cotrip_corridor.py
```

Unit tests only. They do not call the live API.

## Disclosure

- The script calls CDOT's public COtrip API. No key, no account, no telemetry, no stored credentials.
- It does not read another tool's login, and it does not start a background process.
- A watcher is documented in the skill as a separate cron the user must ask for. It is not installed by this plugin.
- Optional travel time is an agent action, not plugin code, and only if a Google Maps key is already in the environment. This plugin does not read or store that key.

## License

MIT
