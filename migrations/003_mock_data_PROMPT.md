# Prompt: generate mock data for the Ledger of Petitions

Paste everything below the line into a new session.

---

Write me a single PostgreSQL script that fills three existing tables with realistic mock data for a support-ticket app. Output one `.sql` file I can paste into a SQL editor. Do not write any Python, and do not create, alter, or drop any table — the schema already exists exactly as described.

## The schema

```sql
public.tickets (
  ticket_id   BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  title       VARCHAR(255)  NOT NULL,
  description VARCHAR(4000) NOT NULL DEFAULT '',
  status      VARCHAR(50)   NOT NULL,   -- 'open' | 'in_progress' | 'resolved'
  priority    VARCHAR(20)   NOT NULL,   -- 'low' | 'medium' | 'high' | 'urgent'
  created_by  VARCHAR(255)  NOT NULL,
  created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
)

public.ticket_messages (
  message_id   BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  ticket_id    BIGINT       NOT NULL REFERENCES public.tickets ON DELETE CASCADE,
  message_text TEXT         NOT NULL,
  author       VARCHAR(255) NOT NULL,
  created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
)

-- A GENERAL change log, not status-only. One row per field that moved.
public.ticket_status (
  status_id  BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  ticket_id  BIGINT       NOT NULL REFERENCES public.tickets ON DELETE CASCADE,
  field      VARCHAR(20)  NOT NULL,   -- 'status' | 'priority'
  from_value VARCHAR(50),             -- NULL only for a ticket's opening rows
  to_value   VARCHAR(50)  NOT NULL,
  changed_by VARCHAR(255) NOT NULL,
  changed_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

Constraints that will reject bad data, so respect them:

- `chk_tickets_priority` — `priority IN ('low','medium','high','urgent')`
- `chk_ticket_status_field` — `field IN ('status','priority')`
- `chk_ticket_status_value` — `(field='status' AND to_value IN ('open','in_progress','resolved')) OR (field='priority' AND to_value IN ('low','medium','high','urgent'))`

## Hard requirements

1. **Never write `ticket_id`, `message_id`, or `status_id` literals.** All three are `GENERATED ALWAYS AS IDENTITY` and an explicit value is rejected. Insert the ticket, capture the generated id, and use it for that ticket's children. A `WITH ... INSERT ... RETURNING ticket_id` chain per ticket, or a `DO $$ ... $$` block looping with a variable, both work — pick one and use it consistently.

2. **The change log must be internally consistent with `tickets`.** This is the part that is easy to get wrong:
   - Every ticket gets exactly two opening rows: `('status', NULL, <its first status>)` and `('priority', NULL, <its first priority>)`.
   - Every later row's `from_value` must equal the `to_value` of the previous row **for that same ticket and field**. No gaps, no contradictions.
   - The final `to_value` for `field='status'` must equal that ticket's `tickets.status`, and likewise for `priority`. A ticket that reads `resolved` must have a history that ends at `resolved`.
   - Never emit a row where `from_value = to_value`.

3. **Timestamps must be coherent.** For each ticket: `created_at` first, then its opening change rows at the same instant, then messages and later changes strictly afterwards and in ascending order. Nothing in the future. Spread `tickets.created_at` across roughly the last 90 days.

4. **Idempotent and reversible.** Wrap the whole thing in `BEGIN; ... COMMIT;`. Start with a commented-out `DELETE FROM public.tickets;` line (the cascades clear the children) so I can uncomment it to reset. Do not truncate anything by default.

## Shape of the data

- **25 tickets.** Roughly 40% `open`, 30% `in_progress`, 30% `resolved`. Priorities weighted toward `medium`/`high`, with only 2–3 `urgent`.
- **8–10 recurring petitioner names** reused across tickets, so the Petitioner filter has something to group by. Plain human names.
- **Titles**: one short line naming the matter, under 80 characters. Not a paragraph.
- **Descriptions**: 2–5 sentences of plausible detail, 200–600 characters. Every ticket gets one — no empty strings.
- **Messages**: 0–5 per ticket, averaging about 2. At least three tickets should have zero, and at least two should have five so the thread view is exercised. Authors should be a mix of the original petitioner and a few support-side names.
- **Change history**: `resolved` tickets should show a realistic path (`open` → `in_progress` → `resolved`), some tickets should show a priority escalation, and a handful should have nothing beyond their two opening rows.

## Tone

This is a support desk with a medieval-ledger skin. Write the content as **ordinary, modern helpdesk tickets** — login failures, billing disputes, broken exports, access requests. Do **not** write medieval flavour text; the theme lives in the UI, not the data. Names should be normal contemporary names.

Include a few messy-but-valid realistic touches: one title at nearly 255 characters, one description near 4000, one petitioner name with an apostrophe (`O'Brien`), and one description containing a double quote and an ampersand — these exercise escaping. Make sure any apostrophes are correctly escaped for SQL.

## Before you give it to me

State how you verified the change log is consistent — specifically, how you checked that every ticket's final `to_value` per field matches its row in `tickets`, and that no `from_value` fails to chain from the preceding row. If you cannot verify it by running it, say so plainly rather than asserting it is correct.

Finish with the two `SELECT` statements I can run afterwards to confirm the load: one counting rows per table, and one that returns any ticket whose latest `status` change disagrees with `tickets.status` (which should return zero rows).
