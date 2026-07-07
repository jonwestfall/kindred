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

For Docker, you do not need to copy the printed host-side
`VAPID_PRIVATE_KEY=/.../config/vapid_private.pem` into `.env`. The VAPID
Compose overlay mounts that file read-only and sets the container path
automatically:

```dotenv
VAPID_PRIVATE_KEY=/run/secrets/kindred_vapid_private.pem
```

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

## Complete setup: VAPID plus Caddy on your own domain

Use this path when you own a DNS name such as `kindred.example.com` and want
Caddy to terminate public HTTPS for Kindred.

1. Point DNS at the Docker host.

   Create an `A` or `AAAA` record for your Kindred hostname:

   ```text
   kindred.example.com -> your server's public IP
   ```

   Ports `80` and `443` must reach the host so Caddy can complete certificate
   issuance and serve HTTPS.

2. Create and edit `.env`.

   ```bash
   cp .env.example .env
   ```

   Set at least:

   ```dotenv
   KINDRED_ADMIN_USERNAME=admin
   KINDRED_ADMIN_PASSWORD=replace-with-a-strong-password
   KINDRED_SESSION_SECRET=replace-with-a-long-random-string
   KINDRED_DOMAIN=kindred.example.com
   ACME_EMAIL=you@example.com
   VAPID_SUBJECT=mailto:you@example.com
   ```

   Generate a strong session secret if needed:

   ```bash
   python3 - <<'PY'
   import secrets
   print(secrets.token_urlsafe(48))
   PY
   ```

3. Generate VAPID keys.

   ```bash
   .venv/bin/python scripts/generate_vapid_keys.py
   ```

   If you have not created the Python environment yet:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -e './backend[notifications]'
   .venv/bin/python scripts/generate_vapid_keys.py
   ```

4. Copy only the public VAPID values into `.env`.

   ```dotenv
   VAPID_PUBLIC_KEY=<value printed by scripts/generate_vapid_keys.py>
   VAPID_SUBJECT=mailto:you@example.com
   ```

   Leave `config/vapid_private.pem` on disk. Do not commit it. The
   `docker/compose.vapid.yml` overlay mounts it into the container.

5. Start Kindred with both overlays.

   ```bash
   docker compose \
     -f docker/compose.yml \
     -f docker/compose.vapid.yml \
     -f docker/compose.domain.yml \
     up -d --build
   ```

6. Verify the merged Compose config if something looks odd.

   ```bash
   KINDRED_DOMAIN=kindred.example.com ACME_EMAIL=you@example.com \
   docker compose \
     -f docker/compose.yml \
     -f docker/compose.vapid.yml \
     -f docker/compose.domain.yml \
     config
   ```

   In the merged output:

   - `caddy` should publish ports `80` and `443`;
   - `kindred` should expose port `8000` to the Compose network;
   - `kindred` should mount `config/vapid_private.pem` read-only at
     `/run/secrets/kindred_vapid_private.pem`.

7. Open and subscribe.

   Open:

   ```text
   https://kindred.example.com
   ```

   Sign in as the administrator, click the notification bell, and allow browser
   notifications. WebSocket updates should work in open tabs; background Web
   Push should work after the VAPID subscription is saved.

8. Check logs.

   ```bash
   docker compose \
     -f docker/compose.yml \
     -f docker/compose.vapid.yml \
     -f docker/compose.domain.yml \
     logs -f kindred caddy
   ```

To stop the stack:

```bash
docker compose \
  -f docker/compose.yml \
  -f docker/compose.vapid.yml \
  -f docker/compose.domain.yml \
  down
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

## Complete setup: VAPID plus Tailscale Serve

Use this path when you want private HTTPS through a Tailscale tailnet name such
as `https://kindred.yak-bebop.ts.net/` without exposing Kindred to the public
internet.

Tailscale runs on the host. Kindred stays in Docker and binds only to
`127.0.0.1`; `tailscale serve` publishes the HTTPS tailnet URL and proxies to
that local port.

1. Prepare Tailscale on the host.

   Install and sign in to Tailscale on the Mac, Raspberry Pi, or server that
   will run Kindred. In the Tailscale admin console, enable MagicDNS and HTTPS
   certificates for the tailnet if they are not already enabled.

   Confirm the host has a tailnet name:

   ```bash
   tailscale status
   ```

2. Create and edit `.env`.

   ```bash
   cp .env.example .env
   ```

   Set at least:

   ```dotenv
   KINDRED_ADMIN_USERNAME=admin
   KINDRED_ADMIN_PASSWORD=replace-with-a-strong-password
   KINDRED_SESSION_SECRET=replace-with-a-long-random-string
   VAPID_SUBJECT=mailto:you@example.com
   ```

   Optional: choose the host port that Tailscale will proxy to:

   ```dotenv
   KINDRED_PORT=8000
   ```

3. Generate VAPID keys.

   ```bash
   .venv/bin/python scripts/generate_vapid_keys.py
   ```

   If this is a Docker-only machine without the Python environment:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -e './backend[notifications]'
   .venv/bin/python scripts/generate_vapid_keys.py
   ```

4. Copy the public VAPID values into `.env`.

   ```dotenv
   VAPID_PUBLIC_KEY=<value printed by scripts/generate_vapid_keys.py>
   VAPID_SUBJECT=mailto:you@example.com
   ```

   Keep `config/vapid_private.pem` on the host. The VAPID overlay mounts it
   into the container at `/run/secrets/kindred_vapid_private.pem`.

5. Start Kindred with the Tailscale and VAPID Compose files.

   ```bash
   docker compose \
     -f docker/compose.tailscale.yml \
     -f docker/compose.vapid.yml \
     up -d --build
   ```

   This publishes Kindred only on localhost:

   ```text
   127.0.0.1:${KINDRED_PORT:-8000} -> container port 8000
   ```

6. Publish the HTTPS tailnet URL.

   ```bash
   tailscale serve --https=443 localhost:${KINDRED_PORT:-8000}
   tailscale serve status
   ```

   On some Linux installations you may need:

   ```bash
   sudo tailscale serve --https=443 localhost:${KINDRED_PORT:-8000}
   ```

7. Open and subscribe.

   Open the HTTPS URL shown by `tailscale serve status`, for example:

   ```text
   https://kindred.yak-bebop.ts.net/
   ```

   Sign in, click the notification bell, and allow browser notifications. The
   page should be a secure context, so the service worker and Push API can be
   used from devices in your tailnet.

8. Check logs and status.

   ```bash
   docker compose \
     -f docker/compose.tailscale.yml \
     -f docker/compose.vapid.yml \
     logs -f kindred

   tailscale serve status
   ```

To stop serving the tailnet URL:

```bash
tailscale serve --https=443 off
```

To stop Kindred:

```bash
docker compose \
  -f docker/compose.tailscale.yml \
  -f docker/compose.vapid.yml \
  down
```

## Notes for Raspberry Pi

- Use lightweight local models; the web app container itself is small, but the
  model backend is the real resource constraint.
- Keep `KINDRED_CLOUD_DRY_RUN=true` unless you intentionally opt into a cloud
  provider and configure rate limits.
- Bind to localhost plus Tailscale Serve for private remote access, or put the
  app behind a trusted LAN reverse proxy.
