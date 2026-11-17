# Telnyx provider — final steps

1. **Set your API key** (skip if you entered it during install): add
   `TELNYX_API_KEY=...` to `~/.duckwork/.env`. Create a key at
   https://portal.telnyx.com/#/app/api-keys

2. **Restart any running `duckwork gateway`** — providers register once per
   process.

3. **Pick a model:**

   `duckwork model` (interactive picker), or
   `duckwork chat --provider telnyx -m moonshotai/Kimi-K3`

Note: the "Enable now?" toggle does not apply to model providers —
selecting the provider is what activates it.
