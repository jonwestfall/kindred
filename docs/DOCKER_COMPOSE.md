# Docker Compose examples

Kindred ships a base Compose file plus focused examples for common local and
home-server deployment shapes.

Docker Compose can merge multiple files with repeated `-f` arguments. Later
files override or extend earlier files, which is how the VAPID and domain
examples are intended to be used.

## Basic local container

```bash
cp .env.example .env
# edit KINDRED_ADMIN_PASSWORD and KINDRED_SESSION_SECRET
docker compose -f docker/compose.example.local.yml up --build
```

Open `http://127.0.0.1:8000` and sign in with the administrator credentials
from `.env`.

The normal project file works the same way:

```bash
docker compose -f docker/compose.yml up --build
```

## Add VAPID keys for Web Push

Generate keys:

```bash
.venv/bin/python scripts/generate_vapid_keys.py
```

Copy the printed `VAPID_PUBLIC_KEY` and `VAPID_SUBJECT` into `.env`. The script
also writes `config/vapid_private.pem`, which is ignored by Git.

Then run:

```bash
docker compose \
  -f docker/compose.yml \
  -f docker/compose.vapid.yml \
  up --build
```

The overlay mounts the private key read-only at
`/run/secrets/kindred_vapid_private.pem` and points `VAPID_PRIVATE_KEY` at that
container path.

## Serve your own domain with Caddy

Set DNS for your domain to the Docker host, then run:

```bash
KINDRED_DOMAIN=kindred.example.com ACME_EMAIL=you@example.com \
docker compose \
  -f docker/compose.yml \
  -f docker/compose.domain.yml \
  up --build
```

Caddy listens on ports `80` and `443`, requests a public certificate, and
reverse-proxies to the `kindred` service. Keep authentication enabled and use a
strong administrator password before exposing a domain.

You can combine domain + VAPID:

```bash
KINDRED_DOMAIN=kindred.example.com ACME_EMAIL=you@example.com \
docker compose \
  -f docker/compose.yml \
  -f docker/compose.vapid.yml \
  -f docker/compose.domain.yml \
  up --build
```

## Serve a Tailscale HTTPS name

Use the standalone Tailscale Compose example:

```bash
docker compose -f docker/compose.tailscale.yml up --build
```

Then, on the host running Tailscale:

```bash
tailscale serve --https=443 localhost:${KINDRED_PORT:-8000}
tailscale serve status
```

Tailscale Serve terminates HTTPS for the machine's tailnet name and proxies to
the local Docker-published port. This keeps the container simple and avoids
mounting Tailscale state into Kindred.

To stop serving:

```bash
tailscale serve --https=443 off
```

## Notes for Raspberry Pi

- Use lightweight local models; the web app container itself is small, but the
  model backend is the real resource constraint.
- Keep `KINDRED_CLOUD_DRY_RUN=true` unless you intentionally opt into a cloud
  provider and configure rate limits.
- Bind to localhost plus Tailscale Serve for private remote access, or put the
  app behind a trusted LAN reverse proxy.
