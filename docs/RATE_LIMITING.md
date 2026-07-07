# Rate limiting and cost protection

Cloud protection is an application guardrail in front of the optional
OpenAI-compatible and image interfaces. It is not a substitute for
provider-side budgets and alerts.

## Configurable limits

| Setting | Default | Meaning |
| --- | ---: | --- |
| Requests per hour | 20 | All cloud tasks in rolling 60 minutes |
| Requests per day | 100 | All cloud tasks in rolling 24 hours |
| Tokens per day | 50,000 | Input plus output tokens in rolling 24 hours |
| Cloud spend ceiling | $2.00 | Estimated rolling 24-hour cost |
| Image generations per day | 2 | Image tasks in rolling 24 hours |

The limiter reads SQLite immediately before a cloud call. A violation returns
HTTP `429`; no provider request is made.

Before a call, tokens are conservatively approximated from character count plus
an output allowance. Afterward, provider usage replaces estimates for the
logged row when available. Cost coefficients are conservative MVP defaults in
`llm.py`; they do not match every provider. Set a lower Kindred ceiling than
your real budget and configure hard limits at the provider too.

## Dry run

`KINDRED_CLOUD_DRY_RUN=true` is the default. Dry-run tasks make no external
request, are visibly labeled, and are written to the usage ledger. They count
toward request/image limits so the control path is testable.

## Daemon limits

The daemon has separate global autonomous messages/hour and messages/day limits,
plus character cooldowns and quiet hours. A cloud-enabled character must pass
both anti-spam and cloud-budget gates.

Inspect current windows in System or:

```bash
TOKEN="$(
  curl -s http://127.0.0.1:8000/api/auth/login \
    -H 'content-type: application/json' \
    -d '{"username":"admin","password":"change-me-now"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])'
)"
curl http://127.0.0.1:8000/api/usage -H "authorization: Bearer $TOKEN"
```

## Concurrency limitation

Usage is recorded after a successful provider response. Two exactly simultaneous
cloud requests could pass the same remaining budget before either writes usage.
Kindred's Pi/home-server deployment normally generates only a small number of
requests at a time. A future hardening pass should reserve budget
transactionally before dispatch.
