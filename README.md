# Stockroom Inventory Management

A local-first inventory application built from **Requirements Document - Inv Mgt Sys - v1.2**. It uses React/Vite, FastAPI, PostgreSQL, and Supabase Auth. Local testing remains the default; a separate, authenticated internet deployment path is provided below.

## Requirements coverage

| Requirement | Priority | Status |
|---|---|---|
| R-01 Create product records | MUST | Implemented (name, SKU, supplier, quantity, reorder point, reorder quantity) |
| R-02 View product records | MUST | Implemented (catalog, dashboard, product detail API) |
| R-03 Edit product records | MUST | Implemented |
| R-04 Update inventory quantity | MUST | Implemented |
| R-05 Manual entry and CSV import | MUST | Implemented; imports upsert by SKU and validate each row |
| R-06 Reorder status | MUST | Implemented: quantity <= reorder point means Reorder |
| R-07 Reorder recommendations | MUST | Implemented in the reorder queue and API |
| R-08 Alerts | MUST | Implemented as an in-app alert view/API |
| R-09 Reorder point for 95% of applicable products | MUST | Each product has a required nonnegative reorder point; all applicable products receive a deterministic status/recommendation. No external prediction is used. |
| R-10 Physical inventory counts | SHOULD | Implemented; stores count event, recorded quantity, counted quantity, note, and variance |
| R-11 Push notifications | SHOULD | Not implemented. In-app alerts are available; email/SMS would require an external integration, which the brief excludes. |
| R-12 Vendor lead time | COULD | Not implemented, as permitted |

Automation, POS/vendor integrations, and external notifications remain excluded. Public hosting is prepared separately for the pilot and requires the secured setup steps below.

## Start locally (Docker Desktop)

1. Install and start Docker Desktop.
2. Copy `.env.example` to `.env` in the project root (PowerShell: `Copy-Item .env.example .env`). The default `AUTH_DISABLED=true` is only for local testing; this lets the UI work without a Supabase project.
3. From this folder run `docker compose up --build`.
4. In another terminal run `docker compose exec api python seed.py` to load 20 sample products. Seeding preserves any existing matching SKUs.
5. Open the app at [http://localhost:5173](http://localhost:5173). FastAPI docs are at [http://localhost:8000/docs](http://localhost:8000/docs); health check: [http://localhost:8000/health](http://localhost:8000/health).
6. To stop: `docker compose down`. To also erase local database contents: `docker compose down -v`.

The database schema is created on API startup from SQLAlchemy models in `backend/app/models.py`. The PostgreSQL database is persisted in the `postgres_data` Docker volume.

## Supabase authentication

The application uses Supabase Auth in the frontend when `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` are supplied. Create a Supabase project and an Auth user, then put its project URL in both `SUPABASE_URL` and `VITE_SUPABASE_URL`, and its anon/public key in `VITE_SUPABASE_ANON_KEY`. Set `AUTH_DISABLED=false`. FastAPI verifies ES256/RS256 tokens against the project's public JWKS endpoint and supports HS256 tokens when `SUPABASE_JWT_SECRET` is set to the legacy JWT secret. Restart Compose after changing environment values. The app uses email/password sign-in for an existing user; account provisioning is managed in Supabase.

Never put a Supabase service-role key in the frontend or commit `.env`. The local Compose file explicitly enables the local-only auth bypass; the API setting itself now fails closed by default.

## Prepare an internet deployment (not published)

The root `Dockerfile` builds the React app and serves it and FastAPI from one HTTPS origin. `render.yaml` prepares a Render web service with authentication required and automatic deploys disabled. No public service has been created from this configuration.

1. Put this project in a private GitHub repository. Do not commit `.env`, credentials, or production data.
2. Create a Supabase project for shared production data and authentication. In its **Connect** panel, choose the **Session pooler** connection (port 5432), which works from IPv4-only hosts. Change a `postgresql://` URL to `postgresql+psycopg://`, add `?sslmode=require`, and URL-encode special characters in the password. Keep this full URL private.
3. In Render, create a Blueprint from the repository and review the `inventory-management-app` service. Provide `DATABASE_URL`, `SUPABASE_URL`, and `SUPABASE_ANON_KEY` as secret/environment values. Set `SUPABASE_JWT_SECRET` only if the Supabase project still signs tokens with the legacy HS256 secret. The anon/publishable key is intended for browser use; never use the service-role key. The API validates the token signature, issuer, audience, and expiration.
4. Confirm `AUTH_DISABLED=false` in the Render service settings before deployment. The service checks that Supabase URL and anon key are present at startup. The app/API share one origin, so browser API calls do not need a permissive cross-origin policy.
5. In Supabase Auth URL settings, set the site URL to the HTTPS address Render assigns and add that address to the allowed redirect URLs. Create or invite the people who should use the inventory; the UI only offers sign-in and does not offer open registration.
6. Review the deployment diff and data destination, then deploy the Blueprint. The API creates its tables at startup. The production database starts separate from local PostgreSQL; local data is not copied automatically. Import only the inventory you intend to share after signing in.

The Blueprint uses Render's free web-service plan for a low-cost trial. Render free services can sleep after inactivity and take longer to respond on the first request; choose a paid always-on plan if that is unsuitable. The service is not public until the Blueprint is created and deployed in a Render account.

All authenticated accounts use the same inventory catalog and can edit it. This version does not include per-user or per-role permissions, so invite only people who should share access to the complete catalog.

## Import format

CSV columns (case-insensitive headers): `sku,name,supplier,quantity,reorder_point,reorder_quantity`. Quantity and reorder point must be nonnegative integers; reorder quantity must be at least 1. Existing SKUs are updated. A starter file is available at `backend/sample_inventory.csv` and in the UI import dialog.

## Tests

With the API dependencies installed and `DATABASE_URL=sqlite:///./test_inventory.db`, run from `backend/`:

```sh
pip install -r requirements.txt
pytest -q
```

The tests cover product CRUD, quantity updates, below/at/above reorder status, recommendation and alert results, manual product creation, CSV import, and physical count variances.

## Main API routes

- `GET/POST /api/products`, `GET/PUT/DELETE /api/products/{id}`
- `PATCH /api/products/{id}/quantity`
- `GET /api/reorders`, `GET /api/alerts`
- `POST /api/import` (multipart CSV upload)
- `POST/GET /api/counts`

FastAPI publishes interactive OpenAPI documentation at `/docs` and schema at `/openapi.json`.
