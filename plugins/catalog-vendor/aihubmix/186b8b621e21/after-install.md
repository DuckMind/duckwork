# AIHubMix provider installed

Nothing further is required on current Duckwork builds. Set a key and run it:

    export AIHUBMIX_API_KEY="AIHUBMIX_XXX"
    duckwork --provider aihubmix --model gpt-5.6-sol

Get a key at <https://aihubmix.com/token>. `duckwork doctor` probes the variable
against the live catalog.

## If the provider does not appear

Builds predating 2026-09-02 discover model providers only under
`~/.duckwork/plugins/model-providers/`, while `duckwork plugins install` clones one
level up, so the plugin lands on disk and never registers. The discovery-side
fix for that mismatch (Fordex/duckwork-agent#76372, landed via #101456)
also picks up plugins already installed the broken way.

Upgrading Duckwork is the real fix. On a build that predates it, move the
directory once:

    mkdir -p ~/.duckwork/plugins/model-providers
    mv ~/.duckwork/plugins/aihubmix ~/.duckwork/plugins/model-providers/aihubmix
    duckwork gateway restart
