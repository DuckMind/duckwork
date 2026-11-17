# quotum provider installed

Put your seat's key in `~/.duckwork/.env`:

    QUOTUM_SEAT_KEY=...

Then run it, or make it the default:

    duckwork --provider quotum -m kimi-k3
    duckwork config set model.provider quotum
    duckwork config set model.default kimi-k3

Get the key at <https://quotum.org/seat>. `/usage` shows the session's spend, what is left and the 20:00 UTC bell. If you run the gateway: `duckwork gateway restart`.
