# Stockroom Inventory Management

A React/Vite and FastAPI inventory application using **MySQL 8** for inventory, accounts, and sessions. Supabase remains an optional PostgreSQL data source for migrations.

## Requirements coverage

| Requirement | Priority | Status |
|---|---|---|
| R-01 Create product records | MUST | Implemented |
| R-02 View product records | MUST | Implemented |
| R-03 Edit product records | MUST | Implemented |
| R-04 Update inventory quantity | MUST | Implemented |
| R-05 Manual entry and CSV import | MUST | Implemented |
| R-06 Reorder status | MUST | Implemented: quantity <= reorder point means Reorder |
| R-07 Reorder recommendations | MUST | Implemented |
| R-08 Alerts | MUST | Implemented as in-app alerts |
| R-09 Reorder point for 95% of applicable products | MUST | Each product requires a nonnegative reorder point |
| R-10 Physical inventory counts | SHOULD | Implemented |
| R-11 Push notifications | SHOULD | Not implemented; external notification integrations remain excluded |
| R-12 Vendor lead time | COULD | Not implemented |

Automation, POS/vendor integrations, and external notifications remain excluded.

## Run locally with MySQL 8

1. Install and start Docker Desktop.
2. From this folder, run `docker compose up --build -d`.
3. In a terminal, run `docker compose exec api python -m app.accounts YOUR_USERNAME` and enter a password at the hidden prompts. Open [http://localhost:5173](http://localhost:5173) to sign in. FastAPI docs are at [http://localhost:8000/docs](http://localhost:8000/docs).
4. If this is a new database and you want the 20 sample products, run `docker compose exec api python seed.py`. Do not seed before migrating existing inventory.
5. Stop containers with `docker compose down`. Avoid `docker compose down -v` until migration is confirmed and you have a backup; it deletes the MySQL and legacy PostgreSQL data volumes.

The local MySQL 8 database is persisted in the `mysql_data` Docker volume. The app creates its tables on startup. The MySQL container is bound to localhost and uses development-only credentials from `docker-compose.yml`.

## Preserve existing PostgreSQL data in MySQL

The migration copies every column in `products` and `physical_counts`, preserves IDs and record relationships, normalizes timezone-aware timestamps to UTC for MySQL, checks the copied rows, and leaves the PostgreSQL source unchanged. It refuses to copy into a destination that already contains rows. Take a backup of both databases before migrating production data.

### Migrate the existing local Docker PostgreSQL volume

The Compose file retains the former `postgres_data` volume in a migration-only PostgreSQL service. The source is not started during normal use.

1. Start the MySQL app as above and wait for it to become ready.
2. Start the old local PostgreSQL volume with `docker compose --profile migration up -d legacy-postgres`.
3. Run `docker compose exec api python migrate_postgres_to_mysql.py`.
4. Check the reported row counts and open the app to confirm the inventory and count history. Keep the PostgreSQL volume until that review is complete.

### Migrate the hosted Supabase PostgreSQL data

1. Provision an empty MySQL 8 database that the migration environment can reach.
2. In a local `.env` file, set `SOURCE_DATABASE_URL` to the Supabase PostgreSQL connection using the `postgresql+psycopg://` scheme, and set `DATABASE_URL` to the MySQL connection using `mysql+pymysql://` with `charset=utf8mb4`. URL-encode special characters in passwords. Keep this file private.
3. Run `docker compose up --build -d` so the API container has both database drivers, then run `docker compose exec api python migrate_postgres_to_mysql.py`.
4. Review the script’s per-table counts and the app data. The script does not modify PostgreSQL. Do not point the live app at MySQL until the copy is verified.
5. Set Dokku’s `DATABASE_URL` to the same MySQL 8 destination and deploy the updated app. Keep the existing PostgreSQL database as a rollback copy until the pilot is confirmed.

For the remote Dokku deployment, configure `DATABASE_URL` on `david-morris-6299-project` to point to the verified MySQL 8 destination before deploying. The Dokku remote supplied for this application is `dokku@iscs2.gcsu.edu:david-morris-6299-project`. Deploying code does not itself migrate or modify database contents.

The source URL and destination must both be reachable from the migration environment. The migration utility only copies into empty MySQL tables, verifies the rows, and does not write to PostgreSQL. Keep PostgreSQL available as a rollback source until the MySQL deployment is checked.
## Authentication and access

An operator provisions each account using `python -m app.accounts YOUR_USERNAME` in an interactive terminal with access to the app's MySQL database. Usernames are case-insensitive. The password prompt hides input and requires at least 15 characters. All accounts can access and edit the shared inventory. FastAPI redirects unauthenticated visitors from `/inventory` to `/login` and serves the inventory page with `Cache-Control: no-store`.

Passwords are hashed with Argon2id. The secure, HTTP-only session cookie contains a random token. MySQL stores its SHA-256 digest and eight-hour expiration. Signing out revokes the session immediately. This design uses opaque random tokens verified against MySQL, so it needs no signing key. API requests that change state require `X-Inventory-Request: 1`; a browser on any separate trusted origin needs explicit CORS permission.

### Dokku rollout

1. Coordinate with the ISCS2 administrator to provision the first account using the new code against the existing MySQL database before switching traffic. The provisioning command creates any missing tables and inserts only the requested account. On a Dokku host that grants one-off access, use `ssh -t dokku@iscs2.gcsu.edu run david-morris-6299-project python -m app.accounts YOUR_USERNAME` when the new image is available. An administrator can also run the same module from a trusted environment with the existing MySQL connection. Test the account in the new build before switching traffic where possible.
2. Keep `SESSION_COOKIE_SECURE=true` and serve the application via HTTPS. Point the deployment at the existing MySQL database through Dokku's protected configuration. Back up the database and confirm the application account can create the two authentication tables.
3. After deployment, verify that `/health` returns 200 and anonymous inventory requests return 401. Sign in, confirm that existing products and count history are available, and sign out. Confirm that a subsequent inventory request returns 401.

If your ISCS2 SSH key can use `mysql:console` but Dokku denies `run`, use the account command locally from `backend/` with the Python dependencies installed:

```sh
python -m app.accounts --iscs2 jim.huskisson
python -m app.accounts --iscs2 phase7.demo
```

The prompt hashes the password locally and sends only the hash and username to the assigned database over SSH. This creates the account table if needed. The deployed app creates the session table at startup.

### Phase 7 demo

Provision a fictional account such as `phase7.demo` using the same account command. Choose a unique demo password at the hidden prompt and put that account's credentials only on the course submission form. Review the deployed products, suppliers, count history and notes, and downloadable samples for fictional data before sharing the demo login. Use a separate MySQL database populated with the fictional seed data if the existing database contains real records.

In a fresh private browser window, open the ISCS2 URL, paste `/inventory` directly, and confirm it lands on `/login`. Sign in with the demo account, sign out, then press Back and confirm you see the login. In the ISCS2 MySQL console, this query verifies the format without printing any of the stored hash:

```sql
SELECT username, password_hash LIKE '$argon2id$%' AS uses_argon2id
FROM inventory_users
WHERE username = 'phase7.demo';
```

### Rotate the exposed MySQL credential

Have the database administrator create a replacement restricted application credential and store it through the approved secret channel. Configure Dokku's `DATABASE_URL` with the replacement using protected access and keep its value out of Git, chat, and deployment logs. Restart the application and verify database access, login, and inventory operations using the replacement. Revoke the exposed credential promptly after verification and check whether any other service used it. Keep the new credential in place if the application code needs to roll back.

## Import format

CSV columns (case-insensitive headers): `sku,name,supplier,quantity,reorder_point,reorder_quantity`. Quantity and reorder point must be nonnegative integers; reorder quantity must be at least 1. Existing SKUs are updated. The import-ready 20-product sample/seed dataset is saved as `Inventory_Management_Import_Data.csv`, `backend/sample_inventory.csv`, and in the UI import dialog. This is the project seed data, not a live database export.

## Tests

From `backend/`, run the tests against a temporary SQLite database:

```sh
pip install -r requirements.txt
pytest -q
```

The tests cover login, logout, invalid credentials, cookie security, request verification for writes, anonymous access, product CRUD, quantity updates, reorder status and alerts, CSV import, and physical count variances.

## Main API routes

- `GET/POST /api/products`, `GET/PUT/DELETE /api/products/{id}`
- `PATCH /api/products/{id}/quantity`
- `GET /api/reorders`, `GET /api/alerts`
- `POST /api/import`
- `POST/GET /api/counts`

FastAPI publishes interactive OpenAPI documentation at `/docs` and its schema at `/openapi.json`.
