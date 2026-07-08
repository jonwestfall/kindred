# Backup, restore, and reset

Administrators can manage whole-system backups from **System**.

## Backup

Click **Download backup** to receive a `.zip` file containing:

- `manifest.json` with version/build and database schema metadata;
- `database/kindred.db`, a consistent SQLite snapshot;
- `uploads/`, if local uploaded files exist.

The backup contains local users, character cards, lore packs, chats, settings,
usage logs, push subscriptions, and cached embeddings. It does not contain
`.env`, API keys, model files, or VAPID private-key files outside the database.

## Restore

Click **Restore backup** and choose a Kindred backup zip. Restore replaces the
current SQLite database and uploaded files. The daemon is paused briefly during
restore and then restarted.

Kindred checks the backup database schema before replacing the live database.
A backup made by a newer Kindred build is rejected with a clear error so the
current database remains intact.

Before restoring, download a fresh backup of the current system if there is
anything you may want later.

## Reset to defaults

Click **Reset to defaults** to delete local runtime state and recreate the
starting database from committed defaults and seed characters.

Reset removes:

- local users;
- conversations and logs;
- imported characters and lore packs;
- uploaded avatars/files;
- usage records and cached embeddings;
- changed settings.

The environment-backed administrator account remains because it comes from
`.env`, not SQLite.

## API routes

- `GET /api/system/backup` downloads a backup zip.
- `POST /api/system/restore` restores a backup zip via multipart upload.
- `POST /api/system/reset` resets local state; the JSON body must be
  `{"confirm":"RESET"}`.

All routes require administrator access.
