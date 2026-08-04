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

Beyond the two existing tables, the app expects one added column:

```sql
ALTER TABLE public.tickets
  ADD COLUMN priority VARCHAR(20) NOT NULL DEFAULT 'medium';

ALTER TABLE public.tickets
  ADD CONSTRAINT chk_tickets_priority
  CHECK (priority IN ('low', 'medium', 'high', 'urgent'));

ALTER TABLE public.tickets
  ADD COLUMN description VARCHAR(4000) NOT NULL DEFAULT '';

CREATE TABLE public.ticket_status (
  status_id   BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  ticket_id   BIGINT       NOT NULL,
  from_status VARCHAR(50),
  to_status   VARCHAR(50)  NOT NULL,
  changed_by  VARCHAR(255) NOT NULL,
  changed_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_ticket_status_ticket FOREIGN KEY (ticket_id)
    REFERENCES public.tickets (ticket_id) ON DELETE CASCADE,
  CONSTRAINT chk_ticket_status_to
    CHECK (to_status IN ('open', 'in_progress', 'resolved'))
);

CREATE INDEX ix_ticket_status_ticket ON public.ticket_status (ticket_id, changed_at);
```

`title` is the one-line name of the matter; `description` is the grievance in full. Existing rows backfill to an empty description and the app shows "No grievance was set down" for those.

The app runs no DDL of its own.

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

Create the secret once with the Databricks CLI:

```powershell
databricks secrets create-scope database
databricks secrets put-secret database lakebase-url --string-value 'postgresql://...'
```

The app service principal needs `READ` on that scope. The password is static and non-expiring, so **rotate it deliberately** — update the Postgres role and the secret together.

## Table permissions

The Postgres role in the URL needs access to the pre-existing tables:

- `SELECT`, `INSERT`, `UPDATE`, and `DELETE` on `public.tickets`
- `SELECT` and `INSERT` on `public.ticket_messages`
- `SELECT` and `INSERT` on `public.ticket_status`
- `USAGE` on the `ticket_status` identity sequence

Deleting a ticket removes its messages **and its status history** through the `ON DELETE CASCADE` foreign keys, so no separate `DELETE` grant is required on either child table.

## Change history

`ticket_status` is a general change log, not a status-only table. Each row records **one field moving**:

| Column | Meaning |
|---|---|
| `field` | `status` or `priority` |
| `from_value` | previous value, `NULL` for the opening entry |
| `to_value` | new value |
| `changed_by` | the hand responsible |

Creating a petition writes two opening rows (one per tracked field). An amendment writes one row per field that actually moved — resubmitting the same values writes nothing. Adding a third tracked field later costs a CHECK constraint, not a new table.

A `CHECK` validates the value against its field, so a priority row can never hold `in_progress`. The read, the update, and the history inserts share one transaction with `SELECT … FOR UPDATE` on the ticket row, so concurrent amendments cannot record a movement that never happened.

Amending requires a **Hand**, since a history of anonymous changes is not worth keeping.

Run `migrations/002_generalise_history.sql` to widen an existing status-only table.

Both primary keys are `GENERATED ALWAYS AS IDENTITY`; the app never supplies `ticket_id` or `message_id`, and it lets `created_at` fall back to its `CURRENT_TIMESTAMP` default.

No permission or schema SQL is run by this repository. A database administrator must grant the applicable access before deployment, and no endpoint, role, or password value belongs in source control.

## Local development

Prerequisites: Python 3.9+, the Databricks CLI, and a Lakebase Postgres role with the table permissions listed above.

1. Authenticate with `databricks auth login`.
2. Set the connection URL directly. This bypasses the secret lookup, so no workspace secret access is needed locally. Do not commit this value.

   ```powershell
   $env:LAKEBASE_URL = 'postgresql://<role>:<password>@<host>:5432/databricks_postgres?sslmode=require'
   ```

   To exercise the deployed path instead, leave `LAKEBASE_URL` unset and the app will read the secret using your CLI credentials.

3. Create an environment and install the packages:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements-dev.txt
   ```

4. Run the application:

   ```powershell
   uvicorn app:app --reload --port 8000
   ```

   Then open http://127.0.0.1:8000.

5. Run the available non-database unit tests:

   ```powershell
   pytest
   ```

## Databricks deployment

1. Store the connection URL in the `database/lakebase-url` secret and grant the app service principal `READ` on that scope. No database resource attachment is required, since the app authenticates with the role in the URL rather than with the service principal's own identity.
2. Ensure that Postgres role has the existing-table privileges listed above. This repository does not manage those grants.
3. Sync the repository to a workspace folder, then deploy it. Replace the placeholders with your own workspace path and app name:

   ```powershell
   databricks sync . /Workspace/Users/<your-email>/support-ticket-manager
   databricks apps deploy <app-name> --source-code-path /Workspace/Users/<your-email>/support-ticket-manager
   ```

4. Open the app URL shown by the deployment. Creation, message, and status changes each commit in Lakebase and immediately refresh the relevant view.

For the resource and token-rotation concepts, see the official [Lakebase resource documentation](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/lakebase) and [custom Databricks App Lakebase tutorial](https://docs.databricks.com/aws/en/oltp/projects/tutorial-databricks-apps-autoscaling).
