# Blinkenbar presentation notes

## Description

A supercomputer-style light panel for Duckwork Desktop, driven by aggregate system counters and live agent activity.

## Visual direction

Preserve the dense light banks, black instrument field, restrained glow and tiny, subdued labels. CM-5-style supercomputer panels are the inspiration, not a claim of hardware emulation. Motion is central: ambient patterns remain alive while actual work changes the activity signatures. The panel should reward familiarity with its rhythms rather than require users to read every light as a meter.

The canvas is passive. Keep actual presentation controls separate from the light field. Do not manufacture task activity for a product capture.

## Public claims

Use the shipped [README](README.md) as the feature and privacy reference. Describe disk fallback as an activity proxy, GPU sampling as optional Windows NVML, and measurements as belonging to the backend host. Do not claim benchmarking, task progress percentages, anomaly detection, audit history, certification, universal platform verification or endorsement by Fordex.

## Catalog image

`docs/media/blinkenbar-catalog-hero.png` is the dedicated 1200×600 **candidate** for the catalog's shared card, wide detail header and Open Graph image. It recomposes the approved CM-5 cabinet artwork, Blinkenbar lettering and actual ProDyn.ai mark inside the measured crop intersection. It is illustrative artwork, not a plugin screenshot. Publication and the catalog pin/image-URL update remain separate, approved steps.

Keep `blinkenbar-prodyn-hero.png` for the README and existing promotional treatment. The older `blinkenbar-catalog.png` remains an actual-plugin panel capture owned by the runtime harness; it is not this candidate. See [media consumers, bounds, regeneration and visual gates](docs/media/README.md) and [runtime capture instructions](scripts/qa/README.md).

## Catalog submission

The [Duckwork plugin catalog](https://duckwork-agent.fordex.com/docs/plugins) accepts maintainer-reviewed pull requests adding a file under `plugin-catalog/` in the [Duckwork repository](https://github.com/DuckMind/duckwork). Follow its [current admission policy](https://github.com/DuckMind/duckwork).

Use the public repository URL, the actual release version, and the exact reviewed commit. Declare the desktop category and community tier; the Python entrypoint currently registers no tools, hooks or middleware and requires no environment variables. Do not infer a minimum Duckwork version. Pin the catalog image to the same commit as the code.

Publishing a repository does not make it a catalog entry. Admission and future updates require maintainer review; each update uses a new commit-pin PR.
