# Android and Render integration

The Django API uses the same User, Device, Report, Alert, UserProfile, and MonitoringArea records as the website. Web signup now requires a unique email, shares the mobile account database, and prevents duplicate email addresses when editing a profile. The Android build defaults to `https://aquawatch.tech/`.

## Deploy the backend on your existing Render service

1. Verify the existing service is connected to this web repository and deploy the changes in `aquawatch/aquawatch_app`, the new migration, and `aquawatch/aquawatch/settings.py`. Avoid deploying the Android repository as the web service.
2. Keep the current SQLite database on a persistent disk. Before attaching a disk or deploying, back up the current **live** database and media; the repository's `db.sqlite3` might not contain the current live records. Confirm the existing disk's mount path, restore the backup there, and set `AQUAWATCH_SQLITE_PATH` to the database's absolute path, for example `/var/data/db.sqlite3`. Keep `DATABASE_URL` unset when using this option; a configured `DATABASE_URL` takes precedence. Optionally set `AQUAWATCH_MEDIA_ROOT=/var/data/media` after preserving the existing uploads. A committed SQLite file in the service directory is not durable storage on Render's default filesystem. See [Render's persistent storage guide](https://render.com/docs/disks). This change does not attach a disk, move existing records, switch databases, or purchase hosting. Without the new environment variables, local database/media paths stay unchanged.
3. Keep the existing root directory and entry point. For the included Blueprint, the root directory is `aquawatch`, the build command is `pip install -r requirements.txt && python manage.py collectstatic --noinput`, and the start command is `python manage.py migrate && gunicorn aquawatch.wsgi:application --log-file -`. If the service uses the repository root instead, prefix the management command with `aquawatch/` and run Gunicorn with `--chdir aquawatch`.
4. Configure mobile signup email using Render environment variables: `EMAIL_HOST`, `EMAIL_PORT` (default 587), `EMAIL_USE_TLS` (default True), `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `DEFAULT_FROM_EMAIL`. For Gmail, use `smtp.gmail.com`, port 587, TLS, the sender's email, and an app password. Keep the password in Render; it is no longer embedded in the Android APK. Existing accounts can log in without these email settings. Choose a mail transport that your Render plan permits.
5. Keep a stable `SECRET_KEY` and the existing `ALLOWED_HOSTS`. Deploying applies migrations `0004` and `0005` before starting the web process. The new tables and nullable fields preserve existing records. Migration `0005` trims and lowercases existing emails, then creates a unique index on non-empty emails in Django's user table. Existing accounts without an email remain intact. If accounts already share an email, migration stops and lists their user IDs; assign each account a distinct verified email and rerun `python manage.py migrate`. It does not delete or merge accounts. Rolling back `0005` removes the index but retains normalized emails. Because the user table belongs to Django's auth app, the index is managed explicitly by this migration; verify/recreate it if a future auth migration rebuilds that table.
6. Verify `GET /api/v1/health/` returns `{"service":"aquawatch","api_version":1}`. A 404 means the API has not been deployed to that service. A health response alone does not verify database access; follow with a login and sync test.

## Test the connection

Install the new Android debug APK. Sign in with your existing web email/password or web username/password. Old accounts that exist only on the phone are not automatically Django accounts: create a server account first, using the same email to import the phone's registered devices. New mobile accounts use their email as the web username.

Create a web account at `/register/`, then log into Android using that email and password. Attempt a second signup on both platforms with the same email, including uppercase letters or surrounding spaces; both must reject it and direct you to sign in. Mobile-created accounts can use their email and password on the web login page. Web-created accounts use their chosen username on the web login page. These rules take effect on Render after deploying the updated backend and running migration `0005`; this change does not require a new Android APK.

In Settings, open **Incident reports** and submit a report. Confirm it reaches the website automatically for that account; **Sync now** remains available for a manual check. Register a device, receive a status or SOS SMS, and confirm the website shows its location and alert after the phone has internet. Create or edit a device on the website, then confirm the foreground phone receives the change during its next refresh. Switch accounts and verify device/report lists are isolated. Repeat an edit while offline, reconnect, and check that the retained event uploads without creating duplicates.

For an alternate HTTPS hostname, add `aquawatch.api.url=https://your-host/` to Android's untracked `local.properties`, then rebuild. Keep the URL at the host root; the client appends `/api/v1/`. Changing the server requires signing in again. The known AquaWatch custom domains and Render hostname share the original phone cache; other servers use separate local storage.

## API contract

| Method | Route | Request |
| --- | --- | --- |
| GET | `/api/v1/health/` | No authentication |
| POST | `/api/v1/auth/login/` | `email` (email or web username), `password` |
| POST | `/api/v1/auth/request-code/` | `email` |
| POST | `/api/v1/auth/register/` | `email`, `password`, `code`, `accepted_terms: true`, `first_name`, `last_name`, `phone`, `role`, `station` |
| POST | `/api/v1/auth/logout/` | Authenticated, empty JSON object |
| POST | `/api/v1/auth/password/` | Authenticated, `current_password`, `new_password` |
| GET/POST | `/api/v1/sync/` | Authenticated; POST accepts `events` |

POST requests must use `Content-Type: application/json`. Protected routes accept `Authorization: Bearer <token>` and do not use browser session cookies. Tokens expire after 30 days, are stored as hashes on the server, and are invalidated by account deactivation or password changes. Login/register/password responses contain `token`, `expires_at`, and `snapshot`. Android encrypts its token with the Keystore in no-backup storage. Email codes expire after five minutes and allow five incorrect attempts. Authentication attempts are limited using database-backed counters.

Example sync request:

```json
{
  "events": [
    {
      "id": "a-persisted-unique-event-id",
      "kind": "device.upsert",
      "data": {"id": "phone-device-id", "name": "Boat 1", "serial": "AW-001", "type": "GPS tracker", "sim": "+639123456789"}
    }
  ]
}
```

Response: `{"accepted":["a-persisted-unique-event-id"],"snapshot":{...}}`. The snapshot includes `user`, `area`, `devices`, `reports`, and `alerts` scoped to the authenticated Django user. `user.id` is the stable account identity. Devices include both a mobile `id` and integer `server_id`; existing web devices initially use IDs such as `web-7`. The app links an existing web device by its serial within that account. Duplicate web serials must be resolved before linking.

| Event kind | Data |
| --- | --- |
| `device.upsert` | `id`, `name`, `type`, `serial`, `imei`, `sim`, `owner`, `driver`, `vessel`, `reg`, `contact` |
| `report.create` | `id`, `type`, `location`, `severity`, `description`, `created_at` |
| `reading.create` | `device_id`, `received_at`, `latitude`, `longitude`, `gyro_x`, `gyro_y`, `gsm_signal`, `acceleration`, `water_level_value`, `is_distress`, `alert_type` |
| `alert.create` | `device_id`, `received_at`, `latitude`, `longitude`, `alert_type`, `is_distress` |
| `alert.dismiss` | `alert_id` |
| `profile.update` | `first_name`, `last_name`, `phone`, `role`, `station` |
| `area.update` | `latitude`, `longitude`, `label` |

Event times are Unix milliseconds; the website receives readable UTC timestamps. Sensor measurements are separate from boolean module capability flags. Readings append history and update the latest position only when newer. Distress/SOS readings also create an Alert in the existing web table. An event ID can be replayed safely, but cannot be reused with different content.

The sync endpoint accepts up to 100 events and 512 KB per request. Android limits upload batches by count and size. A rejected event rolls back its batch and returns `failed_event_id`; Android retains that event under uploads needing attention and continues uploading the other records. Fix/review the rejected data before retrying. Network errors and server outages leave events queued with backoff.

## Current behavior and limits

- Incoming SMS stays the hardware transport. The receiving phone needs internet to forward readings to Render. Each shared-data save persists an event and signals a prompt upload attempt, alongside network-constrained WorkManager recovery. Bursts coalesce without cancelling an upload already in flight. A validated reconnection schedules upload and refresh. Android's background restrictions and network/server availability can delay delivery.
- Android refreshes shared data every 30 seconds while its main screens are visible and on startup/reconnection. Periodic background refresh retains its 15-minute minimum; this is not a push subscription. The visible web Alerts page polls every 5 seconds. Dashboard, Devices and Users check an account-scoped revision every 10 seconds and refresh only after a change. Forms/map editors are excluded so unsaved edits are preserved.
- Reports and queued events are persisted together and partitioned by server plus Django user ID. Existing phone devices are imported only when the local account email matches the authenticated server email. Existing older SMS history remains local; new SMS readings are uploaded.
- Pending phone edits take precedence during a refresh. Conflicting metadata writes use server processing order. Replays do not duplicate reports or alerts.
- Profile/monitoring images stay on the phone; binary photo uploads are not implemented. Notification/display settings remain platform-specific. Password recovery is not implemented by this API.
- The API snapshot currently returns complete lists. Pagination and a separate telemetry ingestion service can be added if data volume grows.
- SQLite uses a 20-second lock timeout and `IMMEDIATE` transactions to serialize sync writes. Keep the disk-backed service as a single instance. See [Django's SQLite guidance](https://docs.djangoproject.com/en/6.0/ref/databases/#sqlite-notes). PostgreSQL remains an optional future scaling path, not a requirement for this implementation.
- No Render account/environment was changed and no production deployment was performed from this workspace. The user deployed the backend separately; its health and protected sync endpoints were verified live on `aquawatch.tech`. Authenticated account sync and email delivery still require testing with a real account.

## Verification

From the web repository with dependencies installed:

```powershell
python aquawatch/manage.py collectstatic --noinput
python aquawatch/manage.py test aquawatch_app --noinput
python aquawatch/manage.py makemigrations --check --dry-run
python aquawatch/manage.py check
```

From the Android repository:

```powershell
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug :app:lintDebug
```


## Alert synchronization and dismissal

Migration 0008 adds device attribution to Alert and an account-scoped
AlertDismissal table. New SMS warnings upload through reading.create. Retained
older real phone alerts are queued once through alert.create; labeled samples
are excluded. Both paths share a device/timestamp identity to prevent duplicates.
alert.dismiss events store durable dismissal keys, even when an alert upload
arrives later. Snapshots return active alerts plus dismissed_alert_ids. Android
merges these with pending offline dismissals. Dismissal preserves alerts and
sensor history, and does not allow access to another user's alerts.

Mobile Alerts syncs on opening or Refresh alerts, alongside automatic uploads and foreground/background refresh.
The web Alerts page refreshes every 5 seconds while visible and offers Refresh.
Web dismiss buttons use CSRF-protected POSTs. Web administrators can dismiss for
the owning account; regular users can dismiss only their own alerts. Deploy the
backend and migration before installing the updated APK on a production account.


## Device identity

The admin devices API now supplies separate device registration fields,
`owner_name` (registered boat owner), and `account` (id, name, username, email).
The older `owner` username alias remains for existing clients. Device names are
always registration names and do not come from SOS/alert types. Android and web
show account, device identification, vessel, contact and tracking information
before history. Empty alert-history panels are omitted on Android; actual
warnings remain in the selected date's recorded device alerts.
