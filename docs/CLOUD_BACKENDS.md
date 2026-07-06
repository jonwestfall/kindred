# Optional cloud backends

Cloud is disabled by design unless a character selects `openai_compatible`.
Local Ollama remains the seeded default. The adapter uses
`POST /chat/completions` and works with providers and self-hosted gateways that
support that OpenAI-compatible shape.

## Configure

```dotenv
OPENAI_COMPATIBLE_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=
OPENAI_COMPATIBLE_MODEL=gpt-4.1-mini
KINDRED_CLOUD_DRY_RUN=true
```

Choose OpenAI-compatible in one character's editor. The UI displays a warning
in both the editor and conversation.

Do not paste API keys into a profile, world notes, or browser field. Set the key
only in `.env` or the deployment secret mechanism.

## Dry run

Dry run is on by default. A cloud-configured character produces a clearly
marked local placeholder response, writes a dry-run usage row, and makes no
external request. After reviewing Settings → Cloud protection:

```dotenv
KINDRED_CLOUD_DRY_RUN=false
```

Restart Kindred to apply environment changes.

## What leaves the device

For an opted-in cloud character, the request includes:

- the character profile;
- up to 20 recent user/character messages;
- optional project/world notes;
- the current message or autonomous-check-in instruction.

It does not include hidden chain-of-thought because Kindred neither requests nor
stores it. The character rationale is an application-generated summary of why
the response was requested.

## Usage and cost

Before dispatch, Kindred checks request/hour, request/day, token/day, and spend
limits. After a response, provider token usage is preferred; otherwise a
conservative text-length estimate is stored. Cost is an estimate, not an
invoice. Provider pricing and caching can differ.

See [Rate limiting](RATE_LIMITING.md) before disabling dry run.

## Image provider placeholder

`POST /api/images/generate` defines a provider-neutral request and applies the
image/day and general cloud limits. In this MVP it supports dry-run only. A live
request returns `501`; no image account is required. A future adapter can
implement the interface without changing character/chat architecture.

## Compatibility

The MVP sends non-streaming chat completions with `model`, `messages`, and
`temperature`. Providers requiring a different authentication scheme, request
path, Responses API, or provider-specific fields need a small adapter.

