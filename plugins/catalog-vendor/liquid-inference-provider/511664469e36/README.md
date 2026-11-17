# Liquid Inference for Duckwork Agent

Adds [Liquid Inference](https://inference.ai.exchange) to
[Duckwork Agent](https://github.com/DuckMind/duckwork) as a model provider.

## Requirements

- Duckwork Agent 0.21.6 or later.
- A Liquid Inference buyer key with the `spend` scope.

## Install

```bash
duckwork plugins install architect-xyz/duckwork-liquid-inference --enable
```

The command asks for `LIQUID_API_KEY` and saves it in `~/.duckwork/.env`.

## Configure

```bash
duckwork config set model.provider liquid
duckwork config set model.default liquid.auto
```

Each request has a cap of 1 USD. To change the cap:

```bash
duckwork config set model.default_headers.x-liquid-cap-usd 0.25
```
