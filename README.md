# Stockroom Inventory Management

A React/Vite and FastAPI inventory application using **MySQL 8**. Supabase Auth was removed; Supabase remains an optional source for the existing PostgreSQL database during migration, but is not used for authentication or as the final application database.

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

Automation, POS/vendor integrations, and external notifications remain excluded. The hosted pilot has no authentication: anyone who can reach it can view and edit the inventory.

## Run locally with MySQL 8

1. Install and start Docker Desktop.
2. From this folder, run `docker compose up --build -d`.
3. Open the app at [http://localhost:5173](http://localhost:5173). FastAPI docs are at [http://localhost:8000/docs](http://localhost:8000/docs).
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

There is no authentication. Anyone who can reach the app can view, add, edit, delete, import, and count inventory. Keep public hosting private or add an access-control layer before sharing the URL.

## Import format

CSV columns (case-insensitive headers): `sku,name,supplier,quantity,reorder_point,reorder_quantity`. Quantity and reorder point must be nonnegative integers; reorder quantity must be at least 1. Existing SKUs are updated. The import-ready 20-product sample/seed dataset is saved as `Inventory_Management_Import_Data.csv`, `backend/sample_inventory.csv`, and in the UI import dialog. This is the project seed data, not a live database export.

## Tests

With the API dependencies installed and `DATABASE_URL=sqlite:///./test_inventory.db`, run from `backend/`:

```sh
pip install -r requirements.txt
pytest -q
```

The tests cover product CRUD, quantity updates, reorder status and alerts, manual entry, CSV import, and physical count variances.

## Main API routes

- `GET/POST /api/products`, `GET/PUT/DELETE /api/products/{id}`
- `PATCH /api/products/{id}/quantity`
- `GET /api/reorders`, `GET /api/alerts`
- `POST /api/import`
- `POST/GET /api/counts`

FastAPI publishes interactive OpenAPI documentation at `/docs` and its schema at `/openapi.json`.
