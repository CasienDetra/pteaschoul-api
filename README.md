# Rental Room API

Rooms, tenants and monthly billing. FastAPI + SQLAlchemy 2.0 + PostgreSQL, managed with `uv`.

A bill is **rent + metered electricity + metered water**:

```
electricity_units = electricity_curr - electricity_prev
water_units       = water_curr      - water_prev
amount = room_price + electricity_units x electricity_rate + water_units x water_rate
```

`room_price`, `electricity_rate` and `water_rate` are snapshotted onto each invoice, so a
bill reissued from last March still adds up after this year's price change. All money is
`Decimal`/`NUMERIC(10,2)`, rounded half-up to cents.

## Billing cycle

| When | What happens |
|---|---|
| 1st of the month, 02:00 | APScheduler creates one invoice per occupied room: rent only, meters carried forward, status `pending` |
| end of the month | staff `PUT /invoices/{id}/reading` with the meter faces → total recomputed |
| `INVOICE_DUE_DAY` of the next month | payment due; `POST /invoices/{id}/payments` accepts full or partial amounts |

Generation is idempotent — one invoice per room per period (`uq_invoice_room_period`), so
re-running it is safe. `POST /invoices/generate` runs the same job by hand.

Opening meter faces come from the tenant's `electricity_start` / `water_start` at check-in,
then from their own previous invoice. Scoped to the tenant, not the room, so an incoming
tenant never inherits the previous occupant's unbilled units.

## Quick start

```bash
cp .env.example .env                    # then set SECRET_KEY: openssl rand -hex 32
docker compose up -d                    # postgres:5432, pgadmin:5050
uv sync
uv run alembic upgrade head
uv run python -m src.app.database.index --rooms 20 --tenants 12
uv run uvicorn src.main:app --reload
```

Docs at http://localhost:8000/docs — log in, then paste the `access_token` into **Authorize**.

Seeded logins: `admin@example.com` / `admin123`, `john@rental.com` / `staff123`,
`tenant1@rental.com` / `tenant123`. Seeder flags: `--rooms`, `--tenants`, `--months`,
`--no-clear`, `--dry-run`, `--seed`.

```bash
uv run python test_billing.py           # the billing arithmetic checks
uv run alembic revision --autogenerate -m "..."   # after editing a model
```

## Roles

| | admin | staff | tenant |
|---|---|---|---|
| create/update/delete users | yes | — | — |
| rooms, tenants, readings, payments | yes | yes | — |
| own invoices and profile | yes | yes | yes |

Role is re-read from the database on every request, so a demotion or deactivation takes
effect immediately rather than at token expiry. Another tenant's invoice returns `404`,
not `403`, so the response cannot be used to probe what exists.

## Endpoints

All under `/api/v1`. Only `POST /login` is open.

| Method | Path | Notes |
|---|---|---|
| POST | `/login` | email + password → JWT, plus device/os/browser info |
| GET | `/me` · POST `/me/password` | own profile |
| POST | `/users` | **admin** — create staff or another admin. `multipart/form-data`, optional `image` |
| GET | `/users` | `page`, `limit`, `role`, `q` |
| GET/PUT/DELETE | `/users/{id}` | PUT/DELETE admin only |
| POST | `/rooms` · GET `/rooms` | filters: `is_available`, `min_price`, `max_price`, `q` |
| GET/PUT/DELETE | `/rooms/{id}` | DELETE admin only, refused while occupied or unpaid |
| GET | `/rooms/reports/monthly` | billed vs collected vs outstanding, plus kWh and m³ |
| POST | `/tenants` | check in; send `email` + `password` to also issue a login |
| GET | `/tenants` · GET `/tenants/{id}` | |
| DELETE | `/tenants/{id}` | check out: frees the room, disables the login, reports the balance |
| POST | `/invoices/generate` | run monthly billing now |
| GET | `/invoices` | `month`, `year`, `room_id`, `tenant_id`, `status`, `overdue` |
| GET | `/invoices/{id}` | itemised bill with its payment ledger |
| PUT | `/invoices/{id}/reading` | record end-of-month meters |
| POST | `/invoices/{id}/payments` | full or partial payment |
| GET | `/invoices/scheduler-status` | jobs and next run time |

## Environment

`DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`,
`ELECTRICITY_RATE`, `WATER_RATE`, `CURRENCY`, `INVOICE_DUE_DAY`, `UPLOAD_DIR`, `LOG_LEVEL`.
`POSTGRES_*` and `PGADMIN_*` are read by `docker-compose.yml` from the same file.

Tariffs are knobs, not constants — set them to your real bill. Changing them affects
future invoices only.

## Known limits

- **Whole-month billing.** A mid-month hand-over leaves the incoming tenant unbilled for
  that month; it is logged as a warning, not pro-rated.
- **No late fees.** `overdue=true` derives lateness from `due_date`; no fee is charged.
- **No meter rollover handling.** A reading below the opening face is rejected (`422`)
  rather than guessed at.
- **In-memory scheduler.** A restart spanning the 1st past the 6-hour misfire window skips
  that run; re-run `POST /invoices/generate` (it is idempotent).
- **No CORS middleware.** Add it when a browser front end appears.
