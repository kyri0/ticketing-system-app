# The Ledger of Petitions

A deployable Databricks App for support ticketing, backed entirely by Lakebase PostgreSQL. View every ticket, expand one to read its message thread, create tickets, add messages, change status and priority, and delete with a confirmation step. No application data is hard-coded.

The interface is a conventional service desk — tally, filters, scannable list, detail card — dressed as a medieval ledger. The structure is deliberately ordinary; only the surface is themed.

## The lexicon

The database stores plain values. The vocabulary is presentation only, and lives in `ticketing/theme.py`.

| Stored | Shown | | Stored | Shown |
|---|---|---|---|---|
| ticket | Petition | | `low` | Trifling |
| `description` | The grievance | | message | Testimony |
| `status` | Standing | | `medium` | Ordinary |
| `priority` | Urgency | | `high` | Pressing |
| `open` | Open | | `urgent` | Dire |
| `in_progress` | Underway | | `created_by` | Petitioner |
| `resolved` | Settled | | message `author` | Hand |

## Stack

FastAPI with Jinja2 templates, server-rendered. No client-side framework and no build step. Every mutation is POST → 303 redirect → GET, so refreshing never resubmits a form, and the expanded petition lives in the URL and can be shared.

## Project layout

- `app.py` — FastAPI routes, filtering, and redirect handling.
- `templates/index.html` — the whole interface, one template.
- `static/ledger.css` — palette, badges, drop caps, layout.
- `ticketing/database.py` — Lakebase connection from the `LAKEBASE_URL` secret.
- `ticketing/repository.py` — transaction-safe, parameterized queries.
- `ticketing/validation.py` — input, status, and priority validation.
- `ticketing/theme.py` — the lexicon and flash-message codes.
- `app.yaml` — Databricks Apps startup configuration.

## Routes

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Ledger. Accepts `standing`, `urgency`, `q`, `sort`, `open` |
| `POST` | `/petitions` | Create |
| `POST` | `/petitions/{id}` | Update standing and urgency |
| `POST` | `/petitions/{id}/messages` | Append to the record |
| `POST` | `/petitions/{id}/delete` | Delete, requires the `sworn` confirmation |
| `GET` | `/health` | Liveness, does not touch the database |

## Required schema

The app expects these existing tables. The repository runs no DDL of its own.

### `public.ticket_messages`

| Column | Type | Notes |
|---|---|---|
| `message_id` | `bigint` | not null |
| `ticket_id` | `bigint` | not null |
| `message_text` | `text` | not null |
| `author` | `varchar(255)` | not null |
| `created_at` | `timestamp` | not null; default `CURRENT_TIMESTAMP` |

### `public.ticket_status`

| Column | Type | Notes |
|---|---|---|
| `status_id` | `bigint` | not null |
| `ticket_id` | `bigint` | not null |
| `from_value` | `varchar(50)` | nullable |
| `to_value` | `varchar(50)` | not null |
| `changed_by` | `varchar(255)` | not null |
| `changed_at` | `timestamp` | not null; default `CURRENT_TIMESTAMP` |
| `field` | `varchar(20)` | not null |

### `public.tickets`

| Column | Type | Notes |
|---|---|---|
| `ticket_id` | `bigint` | not null |
| `title` | `varchar(255)` | not null |
| `status` | `varchar(50)` | not null |
| `created_by` | `varchar(255)` | not null |
| `created_at` | `timestamp` | not null; default `CURRENT_TIMESTAMP` |
| `priority` | `varchar(20)` | not null; default `'medium'` |
| `description` | `varchar(4000)` | not null; default `''` |

`title` is the one-line name of the matter; `description` is the grievance in full. Existing rows backfill to an empty description and the app shows "No grievance was set down" for those.

## Notes on rendering and safety

- Jinja2 autoescaping is on, so ticket titles, authors, and message bodies are escaped by default. Never add `|safe` to a user-supplied value.
- Flash messages travel as codes (`?msg=entered&n=41`) resolved server-side, so no free text from the URL is ever displayed.
- Filter values arriving by query string are checked against the allowed sets before use.
- The `back` field on a form is constrained to same-app paths, so a crafted form cannot turn a redirect into an open redirect.
- Deletion checks the confirmation server-side as well as in the markup.
- The stylesheet is linked root-relative rather than through `url_for()`, which emits an absolute URL that can resolve to `http://` behind an HTTPS proxy and be blocked as mixed content.

## Lakebase connection

The app connects with a single `LAKEBASE_URL` — a standard PostgreSQL connection URL for a native Postgres role with a static password:

```
postgresql://<role>:<password>@<host>.database.cloud.databricks.com:5432/databricks_postgres?sslmode=require
```

That URL is stored in a Databricks secret, so deployment needs one secret rather than a set of connection environment variables. `app.yaml` points at it with `LAKEBASE_SECRET_SCOPE` (default `database`) and `LAKEBASE_SECRET_KEY` (default `lakebase-url`); `ticketing/database.py` reads and base64-decodes it at startup. Setting `LAKEBASE_URL` directly overrides the lookup, which is how local development works.

## Table permissions

Grant the application role access to `public.tickets`, `public.ticket_messages`, and `public.ticket_status` before deployment. The app does not run schema or permission SQL.

## Change history

`ticket_status` is a general change log, not a status-only table. Each row records **one field moving**:

| Column | Meaning |
|---|---|
| `field` | `status` or `priority` |
| `from_value` | previous value, `NULL` for the opening entry |
| `to_value` | new value |
| `changed_by` | the hand responsible |

Creating a petition writes two opening rows (one per tracked field). An amendment writes one row per field that actually moved — resubmitting the same values writes nothing. A future tracked field would reuse the same history table.

The read, the update, and the history inserts share one transaction with `SELECT … FOR UPDATE` on the ticket row, so concurrent amendments cannot record a movement that never happened.

Amending requires a **Hand**, since a history of anonymous changes is not worth keeping.

Both primary keys are `GENERATED ALWAYS AS IDENTITY`; the app never supplies `ticket_id` or `message_id`, and it lets `created_at` fall back to its `CURRENT_TIMESTAMP` default.
