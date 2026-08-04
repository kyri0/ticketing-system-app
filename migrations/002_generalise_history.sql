-- Widen ticket_status from a status-only log into a general change log.
-- One row per field changed, so priority (and anything added later) shares the
-- same table instead of spawning a parallel one.

ALTER TABLE public.ticket_status
  ADD COLUMN field VARCHAR(20) NOT NULL DEFAULT 'status';

ALTER TABLE public.ticket_status RENAME COLUMN from_status TO from_value;
ALTER TABLE public.ticket_status RENAME COLUMN to_status   TO to_value;

-- The old CHECK only allowed the three standings, which would reject every
-- priority row. Replace it with one that validates the value against its field.
ALTER TABLE public.ticket_status DROP CONSTRAINT chk_ticket_status_to;

ALTER TABLE public.ticket_status
  ADD CONSTRAINT chk_ticket_status_field
  CHECK (field IN ('status', 'priority'));

ALTER TABLE public.ticket_status
  ADD CONSTRAINT chk_ticket_status_value
  CHECK (
    (field = 'status'   AND to_value IN ('open', 'in_progress', 'resolved'))
    OR
    (field = 'priority' AND to_value IN ('low', 'medium', 'high', 'urgent'))
  );

-- Existing rows are all status changes; the DEFAULT above already set them.
-- Drop the default so future inserts must say what they are recording.
ALTER TABLE public.ticket_status ALTER COLUMN field DROP DEFAULT;
