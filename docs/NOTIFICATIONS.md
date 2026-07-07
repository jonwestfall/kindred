# Notifications

Kindred uses two delivery paths:

1. a WebSocket event updates open Kindred tabs immediately;
2. optional Web Push wakes the service worker and displays a notification when
   the page is in the background or closed.

WebSocket delivery remains useful on plain HTTP. Background Web Push requires a
service worker and a secure context.

## Browser permission flow

Click the bell in the top bar or Settings → Notifications. Kindred requests
permission, registers `/sw.js`, fetches the VAPID public key, and stores a push
subscription for the signed-in account when VAPID is configured. Without VAPID
it enables in-tab browser alerts and explains that background push is
unavailable.

Permission may be denied permanently for an origin. Reset it in browser site
settings before retrying.

## Generate VAPID keys

```bash
.venv/bin/python scripts/generate_vapid_keys.py
```

The script writes ignored `config/vapid_private.pem` with mode `0600` and prints:

```dotenv
VAPID_PRIVATE_KEY=/absolute/path/to/kindred/config/vapid_private.pem
VAPID_PUBLIC_KEY=<base64url public key>
VAPID_SUBJECT=mailto:you@example.com
```

In Docker, mount the PEM read-only and use its container path.

```bash
docker compose \
  -f docker/compose.yml \
  -f docker/compose.vapid.yml \
  up --build
```

## Secure-context limitation

Service workers and Push API delivery require secure contexts. Modern browsers
treat `http://localhost` as trustworthy for development, but a URL such as
`http://192.168.1.50:8000` usually is not. See MDN's current
[secure-context guidance](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts)
and [Push event documentation](https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerGlobalScope/push_event).

| Access path | Open-tab WebSocket | Service worker / Web Push |
| --- | --- | --- |
| `http://localhost:8000` | Yes | Usually yes |
| `http://LAN_IP:8000` | Yes | Usually blocked |
| `https://trusted-name/` | Yes, via WSS | Yes |

## Local-network HTTPS

Put Kindred behind Caddy, nginx, or another reverse proxy. The certificate must
be trusted on every receiving device.

```caddyfile
kindred.home.arpa {
    tls /etc/caddy/certs/kindred.crt /etc/caddy/certs/kindred.key
    reverse_proxy 127.0.0.1:8000
}
```

Add the hostname to local DNS, generate a certificate with a local CA such as
`mkcert`, and install that CA on each device. Keep Kindred authentication
enabled and use strong credentials before exposing it beyond localhost.

Kindred also ships a Caddy example for public DNS names:

```bash
KINDRED_DOMAIN=kindred.example.com ACME_EMAIL=you@example.com \
docker compose \
  -f docker/compose.yml \
  -f docker/compose.domain.yml \
  up --build
```

For Tailscale HTTPS names, run Kindred on localhost and let the host Tailscale
daemon publish it:

```bash
docker compose -f docker/compose.tailscale.yml up --build
tailscale serve --https=443 localhost:${KINDRED_PORT:-8000}
```

Tailscale Serve terminates HTTPS with a tailnet name such as
`https://kindred.example-tail.ts.net/` and proxies to the local Docker port.

## Privacy and limitations

Browser subscriptions use vendor-operated push endpoints. Payloads are
encrypted, but delivery requires outbound internet and still traverses that
push service. Leave VAPID unset and use open-tab WebSockets if this conflicts
with your privacy requirements.

- Confirm `VAPID_PUBLIC_KEY` has no quotes or whitespace.
- Confirm the private key path is readable by Kindred.
- Confirm `window.isSecureContext` is true.
- Expired subscriptions are removed after a push endpoint returns `404`/`410`;
  click the bell again to subscribe.
- iOS/iPadOS behavior can require adding the site to the Home Screen.
