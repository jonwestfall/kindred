# Notification testing

Use this suite when you want to prove that Kindred messages will reach a phone
instead of only updating an already-open browser tab.

Kindred has two notification paths:

1. open Kindred tabs receive live WebSocket events;
2. subscribed browsers receive Web Push through the service worker when VAPID
   and HTTPS are configured.

The fastest reliable test is the Admin delivery test. The most realistic test
is a forced daemon run.

## iPhone and Tailscale prerequisites

For iPhone background push, use the Tailscale HTTPS URL, not a LAN IP:

```text
https://your-machine.your-tailnet.ts.net
```

On the iPhone:

1. Join the same tailnet.
2. Open Kindred through the Tailscale HTTPS URL.
3. Add Kindred to the Home Screen from Safari's share sheet.
4. Launch Kindred from the Home Screen icon.
5. Sign in as the account you want to test.
6. Tap the bell in the top bar or Settings → Notifications.
7. Accept the browser/iOS notification permission prompt.

Use the same exact origin everywhere. These are different browser origins and
therefore different service-worker subscriptions:

```text
https://macbook.tailnet.ts.net
https://macbook.tailnet.ts.net:8443
http://macbook.local:8000
http://192.168.1.50:8000
```

For iPhone, the Home Screen app path is important. iOS/iPadOS Web Push support
is for Home Screen web apps. Open Safari tabs still receive WebSocket updates
while loaded, but they are not the most reliable way to test background push.

## Test matrix

Run all four cases before relying on notifications.

| Case | Phone state | Expected result |
| --- | --- | --- |
| Active chat thread open | Kindred visible on the tested character's thread | Message appears in the thread; no toast is shown by design. |
| Elsewhere in app | Kindred visible on Admin, Settings, Activity, another thread, etc. | In-app toast appears and the thread list updates. |
| App backgrounded | Home Screen app is in the app switcher or the phone is locked | iOS notification banner/Notification Center item appears. |
| Full daemon path | Same as backgrounded case | A real autonomous character message arrives and is logged. |

If only the open app updates, WebSockets work but background Web Push is not yet
proven.

## Admin interface test

This test sends a logged character message without calling the model. It proves
the delivery fan-out path: database log → WebSocket → toast/service worker →
Web Push.

1. On the iPhone, complete the prerequisites above.
2. Keep the iPhone signed in to the account being tested. For the Admin test,
   that is usually the environment administrator account.
3. On a desktop browser, open the same Kindred origin and sign in as the same
   administrator account.
4. Go to Admin → Notification delivery test.
5. Choose a character.
6. Click Send test message.
7. Confirm the Admin page reports:

   ```text
   Sent to thread #...
   VAPID/Web Push is configured.
   1 saved subscription(s) for this signed-in account.
   ```

   More than one subscription is fine if the same account subscribed from more
   than one browser/device.

8. Confirm the iPhone result:

   - if Kindred is open on the tested thread, the message appears in the thread
     and no toast appears;
   - if Kindred is open elsewhere, an in-app toast appears;
   - if the Home Screen app is backgrounded or the phone is locked, an iOS
     notification appears.
   - tapping the iOS notification opens Kindred to the thread that received the
     message, even if another Kindred page was already open.

9. Open Activity and search for `notification test` or the test message text.
   The row should be logged with backend `kindred`, model
   `notification-test`, and `initiated`.

## Admin interface full-daemon test

This test proves the real autonomous path, including the selected character's
model backend.

1. Make sure the tested character uses a backend that is currently available.
   Check the local model status in the sidebar or System.
2. Go to Settings → Autonomous messages.
3. Choose the character under Test one character now.
4. Confirm the page shows `Forced manual daemon check`.
5. Confirm the iPhone result using the same foreground/background matrix above.
6. Open Activity and confirm the message is logged as `initiated`.

If the daemon test does not create a message, check the note shown in Settings.
Common causes are local model backend unavailable, the character assigned to no
regular users, or testing an admin subscription before the admin has a local
thread for that character. The Admin delivery test creates a thread
automatically and is a better first diagnostic.

## API smoke script

Use the script when you want one command that checks the server-side pieces:

```bash
KINDRED_ADMIN_USERNAME=admin \
KINDRED_ADMIN_PASSWORD='your-password' \
python3 scripts/test_notifications.py https://your-machine.your-tailnet.ts.net
```

For a specific character:

```bash
python3 scripts/test_notifications.py \
  https://your-machine.your-tailnet.ts.net \
  --character-id 1
```

Also test forced daemon generation:

```bash
python3 scripts/test_notifications.py \
  https://your-machine.your-tailnet.ts.net \
  --character-id 1 \
  --daemon
```

Successful output looks like:

```text
Kindred 0.1.0 at https://your-machine.your-tailnet.ts.net
Notification test message: #42 in thread #7
Web Push configured: True
Saved subscriptions for this account: 1
Notification API test passed. Now confirm the banner appeared on the subscribed device.
```

If it fails with `No saved subscription exists`, open Kindred on the iPhone,
tap the bell, allow notifications, and run the script again.

You can authenticate with an existing token instead of username/password:

```bash
KINDRED_API_TOKEN='token-from-login' \
python3 scripts/test_notifications.py https://your-machine.your-tailnet.ts.net
```

## Manual API test with curl

Set the origin and login:

```bash
BASE=https://your-machine.your-tailnet.ts.net
TOKEN=$(
  curl -fsS "$BASE/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d '{"username":"admin","password":"your-password"}' |
  python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])'
)
```

Check VAPID status:

```bash
curl -fsS "$BASE/api/notifications/public-key" \
  -H "Authorization: Bearer $TOKEN"
```

Expected:

```json
{"public_key":"...","web_push_configured":true}
```

List characters and choose an ID:

```bash
curl -fsS "$BASE/api/characters" \
  -H "Authorization: Bearer $TOKEN"
```

Send the delivery-path test:

```bash
curl -fsS "$BASE/api/notifications/test" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"character_id":1,"content":"Kindred curl notification test."}'
```

Expected fields:

```json
{
  "status": "sent",
  "web_push_configured": true,
  "subscription_count": 1,
  "thread_id": 7,
  "message": {
    "sender": "character",
    "backend": "kindred",
    "model": "notification-test",
    "initiated": true
  }
}
```

Then force a real daemon message:

```bash
curl -fsS -X POST "$BASE/api/daemon/run-once?character_id=1" \
  -H "Authorization: Bearer $TOKEN"
```

Expected:

```json
[
  {
    "character_id": 1,
    "initiate": true,
    "note": "Forced manual daemon check",
    "message_count": 1
  }
]
```

Finally, verify the log:

```bash
curl -fsS "$BASE/api/logs?keyword=Kindred%20curl%20notification%20test" \
  -H "Authorization: Bearer $TOKEN"
```

## Testing regular user accounts

Notifications are saved per account. To test a regular user:

1. In Admin, create or enable the user.
2. Grant that user access to the character being tested.
3. On the iPhone, sign in as that user and tap the bell.
4. Run `scripts/test_notifications.py` with that user's username/password, or
   use `KINDRED_API_TOKEN` from that user's login.

The Admin delivery test sends to the currently signed-in admin account. It does
not impersonate regular users.

## Troubleshooting

- `web_push_configured` is `false`: set `VAPID_PUBLIC_KEY`,
  `VAPID_PRIVATE_KEY`, and `VAPID_SUBJECT`; restart Kindred.
- `subscription_count` is `0`: the tested account has not subscribed from this
  exact origin. Open the Tailscale HTTPS URL on the device and tap the bell.
- iPhone receives nothing while locked: launch Kindred from the Home Screen
  icon, not a plain Safari tab, then tap the bell again.
- Open app updates but no system notification appears: WebSocket works; check
  iOS Settings → Notifications → Kindred, Focus modes, and whether the Home
  Screen app was installed from the same URL.
- Desktop gets a notification but iPhone does not: the desktop and iPhone are
  probably different subscriptions. Test `subscription_count`, re-subscribe on
  iPhone, and confirm both use the same Tailscale origin.
- No daemon message: verify the model backend is available, the character has
  nonzero initiative, the user has character access, and quiet hours/rate
  limits are not blocking scheduled runs. The forced daemon API bypasses
  scheduling gates but still needs a working model backend.
- Behind a firewall: browser push endpoints require outbound internet access.
  For iPhone Web Push, allow Apple push endpoints such as `*.push.apple.com`.

## What this suite does and does not prove

The Admin delivery test and `/api/notifications/test` endpoint prove that
Kindred can publish, log, and fan out a character-message event to the current
account. They do not call the LLM.

The forced daemon test proves the model-backed autonomous message path and then
uses the same notification fan-out. It is the closest test to a real chatbot
spontaneously messaging the user.

No server-side test can prove the user noticed the banner. Always include one
human-observed iPhone lock-screen/background test before relying on alerts.
