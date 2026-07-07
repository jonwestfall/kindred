# Authentication and multi-user accounts

Kindred includes a small local authentication layer for home, LAN, and tailnet
deployments.

## Account model

- The administrator account is configured in `.env`.
- Regular users are stored in SQLite.
- Administrators can create, edit, disable, and delete regular users.
- Administrators can choose which characters each regular user may chat with.
- Administrators can view and export all chats.
- Regular users can view only assigned characters and their own threads/logs.

The administrator is intentionally not stored in SQLite. If the database is
lost, corrupted, or misconfigured, you can still recover by editing `.env` and
restarting Kindred.

## Required `.env` settings

```dotenv
KINDRED_AUTH_ENABLED=true
KINDRED_ADMIN_USERNAME=admin
KINDRED_ADMIN_PASSWORD=change-me-now
KINDRED_SESSION_SECRET=replace-with-a-long-random-string
KINDRED_SESSION_HOURS=168
```

Before using Kindred beyond your own development machine:

1. change `KINDRED_ADMIN_PASSWORD`;
2. replace `KINDRED_SESSION_SECRET` with a long random value;
3. restart the backend/container.

Example secret generation:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

## Managing users

Log in as the `.env` administrator and open **Admin**.

From there you can:

- add a user with username/password;
- reset a password by editing the user and entering a new one;
- disable an account without deleting its chat history;
- delete an account;
- assign or remove character access.

Disabling a user takes effect on the next authenticated API call, even if the
browser still has an old session token.

## Access rules

| Capability | Administrator | Regular user |
| --- | --- | --- |
| Create/edit/delete characters | Yes | No |
| Chat with characters | Any character | Assigned characters only |
| View activity/logs | All conversations | Own conversations only |
| Export Markdown/JSON logs | All conversations | Own conversations only |
| Change daemon/rate/notification settings | Yes | No |
| Create/disable/delete users | Yes | No |

The current MVP stores bearer tokens in browser `localStorage`. This is simple
and works well for local deployments, but it is not a substitute for a hardened
internet-facing auth stack. Use HTTPS on any shared network and avoid installing
untrusted browser extensions on machines that administer Kindred.

## Turning auth off for isolated testing

Set:

```dotenv
KINDRED_AUTH_ENABLED=false
```

The API then behaves as a local administrator. This is useful for isolated
test harnesses only; do not use it on a LAN, public host, or shared tailnet.
