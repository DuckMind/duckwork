# Ace Data Cloud model provider for Duckwork Agent

[简体中文使用指南](readme/README_zh_Hans.md)

![Ace Data Cloud](assets/catalog.png)

Maintained by [Ace Data Cloud](https://platform.acedata.cloud?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=acedatacloudmodelproviderduckwork_readme_platform). This plugin adds **Ace Data
Cloud** to Duckwork's model and setup pickers using its public Chat Completions API.
It requires Duckwork 0.21.5 or later and is listed in the
[official Duckwork plugin catalog](https://duckwork-agent.fordex.com/docs/plugins/acedatacloud)
as a community plugin. It is installed separately and is not bundled with Duckwork.

## Native model selection and current distribution

After this named provider plugin is installed, **Ace Data Cloud** appears in
Duckwork's own `duckwork model` / setup picker. Choose it, enter your Ace API Token
and select `gpt-4.1-mini` or `gpt-4.1`; the endpoint and Chat Completions transport
are supplied by the profile. Users do not need to type an API base URL.

This is an official-catalog **community plugin**, installed separately. A fresh
Duckwork installation does not list Ace until the plugin is installed: it is not
bundled or enabled by default. Duckwork's current
[third-party integration policy](https://github.com/DuckMind/duckwork)
requires new vendor integrations to remain standalone; the presence of older
bundled providers is not approval for adding another vendor to core.

The [official model configuration guide](https://duckwork-agent.fordex.com/docs/user-guide/configuring-models)
shows the real Models → Change → provider/model picker. Its historical screenshots
show other providers, not an Ace run. The named Ace picker and credential/endpoint
resolution are validated against unmodified Duckwork 0.21.6 and 0.22.2 in fresh profiles;
this does not claim default bundling, a current GUI run, or new paid inference.

For music, video and images, install the separate
[Ace Data Cloud Media](https://duckwork-agent.fordex.com/docs/plugins/acedatacloud-media)
plugin and enable the service toolset you need. It supports service-name discovery
and [Suno, Seedance, HappyHorse, GPT Image and Nano Banana guides](https://github.com/DuckMind/duckwork).
The model provider itself adds no media tools.

![Edited preview of the Duckwork model picker with Ace; not an actual runtime screenshot](assets/tutorial/duckwork-model-picker-preview.png)

**Official-screenshot edit preview, not an Ace execution screenshot.** Edited
2026-10-17 from the official historical v0.11.0 screenshot (capture date unknown).
It illustrates the provider/model picker after installation, not default bundling,
new paid calls or current GUI validation. [Source and limits](assets/tutorial/SOURCE.md).

## Get your Ace Data Cloud API key

1. Open [Ace Data Cloud → Applications](https://platform.acedata.cloud/console/applications?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=acedatacloudmodelproviderduckwork_readme_api_key). Sign in, or register an account first.
2. Find **General application**. If it has not been created, choose **Initialize General Application**. A general key can use the services available to your account; a dedicated application's key is limited to its service. Check the required service/model access and [current pricing](https://platform.acedata.cloud/models?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=acedatacloudmodelproviderduckwork_readme_pricing).
3. Copy the **API Key** from the application card, or open **Keys / Manage Keys → Create** to create a separate key for this integration. Give it a recognizable name so you can revoke or rotate it independently.
4. When creating a key, review **Expiration Time**, **Set Usage Limitation**, and **Allowed APIs**. Enable only the restrictions you need, allow the operations you will call, then click **Create** and copy the token from the key list. Task lookup does not grant permission to submit a generation. Confirm the application's balance can cover your first request; any trial allowance is whatever your account currently displays.
5. Copy only the token value, without quotation marks, spaces, or `Bearer `. An API Key / API Token field expects this raw value; only a manually configured HTTP `Authorization` header needs the `Bearer ` prefix. A `platform-...` account-management token cannot replace a generation API key.

![Copy an application API key or open Manage Keys](https://raw.githubusercontent.com/AceDataCloud/NanoBananaDify/2522b2f57210597af2db866445319334a1677a23/_assets/tutorial/get-api-key-en.png)

![Create a separately named key with optional restrictions](https://raw.githubusercontent.com/AceDataCloud/NanoBananaDify/2522b2f57210597af2db866445319334a1677a23/_assets/tutorial/create-api-key-en.png)

Save the key in the client's credential store or the environment variable shown below. Never put it in a prompt, shared workflow, screenshot, or Git commit. If authentication fails, check the full copied value, application/service access, expiration, usage limit, and balance before creating another key.

## Install and configure

```sh
duckwork plugins install acedatacloud --enable
duckwork model
```

The catalog installs its reviewed source commit. For the latest repository version,
use `duckwork plugins install AceDataCloud/AceDataCloudModelProviderDuckwork --enable`.
Repository releases and catalog pin updates are published separately.

Choose **Ace Data Cloud**, enter your API key, then select `gpt-4.1-mini` or
`gpt-4.1`. Get a key from your application in the
[Ace Data Cloud console](https://platform.acedata.cloud/console/applications?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=acedatacloudmodelproviderduckwork_readme_api_key).
Enable the required chat service on that application. Keys scoped to other
services cannot make chat requests.

For an environment-based setup, set `ACEDATACLOUD_API_KEY` in the active Duckwork
profile's `.env` file. Keep credentials out of `config.yaml` and source control.
Then run:

```sh
duckwork chat --provider acedatacloud --model gpt-4.1-mini --oneshot "Reply only OK"
```

The plugin supplies the base URL `https://api.acedata.cloud/openai` and the
`chat_completions` transport. No custom-provider YAML is needed. Install it in
each Duckwork profile that should use it.

## Supported models

The picker offers `gpt-4.1-mini` and `gpt-4.1`. Both support text conversations,
streaming tool calls and subsequent tool-result turns. The plugin filters the
live catalog to these tested models; if the catalog is unavailable, the same
two IDs remain available in the picker. This is a picker list, not automatic
model substitution.

Ace Data Cloud's shared `/models` response also contains image-generation and
other-protocol models. They are intentionally excluded. This plugin does not
claim support for the full catalog, Responses, Messages, vision, prompt caching
or configurable reasoning. New model families will be added after validating
their Duckwork transport behavior.

Calls use your Ace Data Cloud balance. See the
[current model catalog and pricing](https://platform.acedata.cloud/models?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=acedatacloudmodelproviderduckwork_readme_pricing) and
your application's package rate. Duckwork may not have an accurate cost estimate
for this provider; the Ace Data Cloud usage and billing records are authoritative.

## Data and permissions

- Duckwork sends chat messages, configured tool schemas and tool results to
  `https://api.acedata.cloud/openai/chat/completions` with your API key. Model
  discovery calls `https://api.acedata.cloud/openai/models` through Duckwork's
  standard credentialed client. A user-configured base URL overrides both.
- The plugin declares only `ACEDATACLOUD_API_KEY`; Duckwork manages that secret.
  It does not read other applications' credentials, write files, run shell
  commands, start background processes, install dependencies or update itself.
- It registers one model-provider profile. There are no tools, hooks,
  middleware, telemetry or automatic model fallbacks in the plugin.
- Updates installed from the Duckwork catalog require a reviewed SHA pin update
  and `duckwork plugins update acedatacloud`.

## Troubleshooting and support

For authentication errors, check the active profile's key and application
permissions. For quota or credit errors, inspect the application's balance.
For rate limits, retry later. The plugin leaves API errors to Duckwork's standard
error handling rather than converting them into successful responses.

Report plugin issues in this repository. Account and billing support is
available through the [Ace Data Cloud console](https://platform.acedata.cloud?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=acedatacloudmodelproviderduckwork_readme_platform).

## Development

Tests use a real Duckwork checkout, isolated temporary homes and a local HTTP
server. CI uses Duckwork's official validation action against the stable release
and a pinned main commit. With a prepared Duckwork interpreter, run:

```sh
DUCKWORK_SOURCE=/absolute/path/to/duckwork-agent python -m unittest discover -s tests -v
```

Validate the installable plugin before publishing:

```sh
duckwork plugins validate /absolute/path/to/AceDataCloudModelProviderDuckwork --install-deps
```

Live checks use only disposable Duckwork homes and explicitly supplied test keys.
