# OpenMail installed

1. `duckwork openmail setup`

   Prompts for a key from https://console.openmail.sh (any scope), picks or creates the inbox,
   asks who may email the agent (list addresses, let OpenMail's sender rules decide, or decide later),
   and writes `~/.duckwork/.env`. `-y` alone never opens the sender gate; pass `--allow-all` for that.

2. `duckwork gateway restart`

3. Email the agent. In channel mode (default) its answer is the reply.

`duckwork openmail doctor` checks the setup. Docs: https://github.com/DuckMind/duckwork
