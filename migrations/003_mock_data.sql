-- Mock data for the Ledger of Petitions support-ticket application.
-- To reset this fixture set, uncomment the next line.  Child rows cascade.
-- DELETE FROM public.tickets;

BEGIN;

DO $seed$
DECLARE
  item jsonb;
  new_ticket_id bigint;
  created_on timestamp;
  first_priority text;
  description_text text;
  title_text text;
  message_total integer;
  message_number integer;
  ticket_number integer := 0;
  support_author text;
  support_authors text[] := ARRAY['Maya Chen', 'Daniel Ruiz', 'Priya Shah', 'Jordan Lee'];
  ticket_data jsonb := $data$
[
  {"title":"Cannot sign in after password reset","description":"I completed the password reset flow this morning and received the confirmation email. The new password is rejected on both the web app and mobile app, while the old password no longer works. I have tried an incognito window and cleared saved credentials, but the result is the same.","status":"open","priority":"high","initial_priority":"medium","created_by":"Nora Patel","messages":2},
  {"title":"Invoice shows duplicate charge for July subscription","description":"Our July invoice contains two charges for the same Pro subscription renewal. The card statement also shows both pending transactions. Please confirm whether one of them will be reversed and let us know when the corrected invoice will be available.","status":"open","priority":"medium","initial_priority":"medium","created_by":"Marcus Green","messages":1},
  {"title":"CSV export stops at 10,000 rows","description":"The customer export completes successfully but only includes the first 10,000 rows. Our account has a little over 18,000 active customers, and the missing records are not available in a second file. This started after we changed the export to include archived contacts.","status":"in_progress","priority":"high","initial_priority":"low","created_by":"Liam O'Brien","messages":3},
  {"title":"Request access for new finance analyst","description":"Please add read-only access to billing reports for our new finance analyst. They need to view invoices and usage summaries but should not be able to change payment methods or invite users. Their company email is ready and can be shared securely if needed.","status":"open","priority":"low","initial_priority":"low","created_by":"Elena Rossi","messages":0},
  {"title":"Production API requests returning 401","description":"Our production integration began receiving 401 responses shortly after midnight. The same API key worked yesterday and no configuration was changed on our side. This is blocking order synchronization, so we need help confirming whether the key was disabled or a service-side change was deployed.","status":"in_progress","priority":"urgent","initial_priority":"high","created_by":"Ben Carter","messages":2},
  {"title":"Shared dashboard does not load for invited users","description":"People invited to our shared dashboard can open the link but see a permanent loading spinner. Administrators can still view the dashboard normally. We tested with two different invited accounts and browsers, and the issue persists after removing and re-adding an invitation.","status":"resolved","priority":"high","initial_priority":"medium","created_by":"Aisha Khan","messages":5},
  {"title":"Need copy of receipts for March and April","description":"Could you send downloadable receipts for our March and April payments? The billing page currently lists the transactions but the receipt buttons return an error. These documents are needed for our monthly expense reconciliation by the end of the week.","status":"open","priority":"medium","initial_priority":"medium","created_by":"Tom Becker","messages":1},
  {"title":"Two-factor code never arrives by SMS","description":"I enabled two-factor authentication and the setup completed, but I never receive the text message during sign-in. My phone number is correct and I can receive texts from other services. Email recovery still works, but I would like the SMS method restored.","status":"in_progress","priority":"high","initial_priority":"high","created_by":"Grace Wilson","messages":3},
  {"title":"Unable to edit existing automation rule","description":"An automation rule created last month now opens in read-only mode for every workspace administrator. We can create a new rule, but we cannot change its conditions or disable it. The rule is still running and is sending notifications to the wrong team.","status":"open","priority":"medium","initial_priority":"medium","created_by":"Victor Nguyen","messages":2},
  {"title":"Requested audit log for former administrator","description":"We need an audit log covering the last 60 days for a former administrator account. The standard audit page only lets us export a shorter period. Please advise whether support can provide the complete activity record or enable a longer export window.","status":"open","priority":"medium","initial_priority":"low","created_by":"Nora Patel","messages":4},
  {"title":"Webhook delivery retries are delayed","description":"Webhook events are arriving, but retry attempts are delayed by several hours instead of the configured interval. This affects failed inventory updates and leaves downstream systems out of date. We have included request IDs from three delayed deliveries in the ticket attachments.","status":"in_progress","priority":"high","initial_priority":"medium","created_by":"Marcus Green","messages":0},
  {"title":"Please remove a former contractor from workspace","description":"A former contractor still appears in our workspace member list even though their account was deactivated. We need their access removed before the next project review. No files need to be deleted; only the workspace membership should be revoked.","status":"resolved","priority":"low","initial_priority":"low","created_by":"Liam O'Brien","messages":2},
  {"title":"Search results omit records with accented names","description":"Search does not return customers whose names contain accented characters unless we enter an exact partial match. For example, a search for a surname without its accent returns nothing. This makes it difficult for our support team to find existing records quickly.","status":"open","priority":"high","initial_priority":"high","created_by":"Elena Rossi","messages":1},
  {"title":"Billing portal reports account past due in error","description":"The billing portal says our account is past due even though the invoice was paid last week and the payment is listed as settled. This warning prevents us from changing our plan. Please correct the account status and confirm that service will not be interrupted.","status":"resolved","priority":"urgent","initial_priority":"medium","created_by":"Ben Carter","messages":5},
  {"title":"Team members cannot download generated PDF reports","description":"Generated PDF reports preview correctly in the browser, but the Download button does nothing for non-admin users. Administrators can download the same files without issue. We tested on current versions of Chrome and Edge with browser extensions disabled.","status":"in_progress","priority":"medium","initial_priority":"medium","created_by":"Aisha Khan","messages":3},
  {"title":"Data import rejected valid ISO date column","description":"Our CSV import is rejecting a date column that uses the ISO format YYYY-MM-DD. The preview labels every value as invalid even though the template describes that format as supported. Other columns in the same file validate and import successfully.","status":"resolved","priority":"high","initial_priority":"low","created_by":"Tom Becker","messages":2},
  {"title":"Notification email arrived without attachment","description":"The notification email for a completed report says an attachment is included, but no file is attached. The report is visible in the application, so the job itself appears to have completed. This has happened for the last two scheduled reports.","status":"open","priority":"medium","initial_priority":"medium","created_by":"Grace Wilson","messages":0},
  {"title":"SSO login loops back to identity provider","description":"Employees using SSO are sent back to the identity provider immediately after completing authentication. No error appears in the browser, and direct password login is disabled for these users. The issue affects our entire organization rather than a single account.","status":"in_progress","priority":"high","initial_priority":"medium","created_by":"Victor Nguyen","messages":4},
  {"title":"Usage total increased after cancelled add-on","description":"Our usage page still includes an add-on that was cancelled before the current billing period started. The expected charge should not be part of this month's estimate. Please verify the calculation before the invoice is finalized.","status":"resolved","priority":"urgent","initial_priority":"high","created_by":"Nora Patel","messages":2},
  {"title":"Need clarification on data retention setting","description":"The data retention settings page lists a 30-day option, but the help article mentions 60 days for our plan. We need to know which setting will apply before enabling automatic deletion. A written confirmation would help our compliance team document the decision.","status":"open","priority":"low","initial_priority":"low","created_by":"Marcus Green","messages":3},
  {"title":"Workspace timezone changes are not saved","description":"Changing the workspace timezone appears to save, but the page reverts to the previous timezone after refresh. Scheduled reports continue to run using the old timezone as well. We need this corrected before next week's regional reporting cycle.","status":"in_progress","priority":"medium","initial_priority":"low","created_by":"Liam O'Brien","messages":1},
  {"title":"Public link should require a passcode","description":"We need to add a passcode to an existing public link for a shared report. The settings page offers the option for new links only, and creating a replacement would require updating many recipients. Please let us know whether the protection can be enabled without changing the URL.","status":"resolved","priority":"high","initial_priority":"high","created_by":"Elena Rossi","messages":2},
  {"title":"Request confirmation that archived projects remain excluded from active-license counts and that the reporting page will preserve this exclusion after the scheduled usage-calculation refresh, because our current report appears to combine archived and active project members in the same total","description":"Our licensing report suddenly includes members from archived projects in the active-license count. The total is now higher than our active directory count and could affect renewal planning. We need confirmation of the expected behavior and a correction before the procurement review on Friday.","status":"resolved","priority":"medium","initial_priority":"medium","created_by":"Ben Carter","messages":3,"long_title":true},
  {"title":"Mobile app crashes when uploading HEIC image","description":"The mobile app closes immediately when a user tries to attach a HEIC image from an iPhone. JPG uploads work normally from the same device. The crash happens before the ticket draft is saved, so users must start again after converting the image.","status":"in_progress","priority":"high","initial_priority":"medium","created_by":"Aisha Khan","messages":1},
  {"title":"Monthly activity export is missing last week's records","description":"The monthly activity export completed without an error, but it is missing events from last week. The dashboard still shows those events, so the underlying data appears present. We need the export corrected for an internal review, and the affected report contains a \"manager approval\" column & a related timestamp.","status":"open","priority":"medium","initial_priority":"medium","created_by":"Tom Becker","messages":2,"long_description":true}
]
$data$;
BEGIN
  FOR item IN SELECT value FROM jsonb_array_elements(ticket_data)
  LOOP
    ticket_number := ticket_number + 1;
    -- The generated dates range from 87 to 15 days ago, so every event is in the past.
    created_on := CURRENT_TIMESTAMP - interval '90 days' + (ticket_number * interval '3 days');
    first_priority := item->>'initial_priority';
    title_text := item->>'title';
    description_text := item->>'description';

    -- Exercise the title and description limits without bypassing the schema.
    IF COALESCE((item->>'long_title')::boolean, false) THEN
      title_text := left(
        'Licensing report mixes active and archived project members during the scheduled usage calculation refresh and affects renewal planning'
        || repeat(' — please review', 9),
        250
      );
    END IF;

    IF COALESCE((item->>'long_description')::boolean, false) THEN
      description_text :=
        'Our monthly activity export completed without an error but omitted events from the previous week, even though those same events remain visible in the dashboard and in individual customer timelines'
        || repeat(' and the missing records include normal user activity, system updates, and manager approvals needed for the internal review', 14)
        || '. The report is used by finance and compliance to reconcile support activity, so we need a corrected file that includes every event with its original timestamp and associated account'
        || repeat(' while preserving the selected filters, column order, and CSV formatting used by our scheduled delivery', 14)
        || '. Please also confirm why the job reported success, whether any other exports created this month are affected, and when we can safely rerun the report without losing the current audit trail.';
    END IF;

    INSERT INTO public.tickets (title, description, status, priority, created_by, created_at)
    VALUES (title_text, description_text, item->>'status', item->>'priority', item->>'created_by', created_on)
    RETURNING ticket_id INTO new_ticket_id;

    -- The two opening rows are deliberately simultaneous with ticket creation.
    INSERT INTO public.ticket_status (ticket_id, field, from_value, to_value, changed_by, changed_at)
    VALUES
      (new_ticket_id, 'status', NULL, 'open', item->>'created_by', created_on),
      (new_ticket_id, 'priority', NULL, first_priority, item->>'created_by', created_on);

    -- A priority move is always chained from its opening value and comes before status moves.
    IF first_priority <> item->>'priority' THEN
      INSERT INTO public.ticket_status (ticket_id, field, from_value, to_value, changed_by, changed_at)
      VALUES (new_ticket_id, 'priority', first_priority, item->>'priority', support_authors[((ticket_number - 1) % 4) + 1], created_on + interval '4 hours');
    END IF;

    -- Status paths are generated from the same final value stored on the ticket.
    IF item->>'status' IN ('in_progress', 'resolved') THEN
      INSERT INTO public.ticket_status (ticket_id, field, from_value, to_value, changed_by, changed_at)
      VALUES (new_ticket_id, 'status', 'open', 'in_progress', support_authors[(ticket_number % 4) + 1], created_on + interval '8 hours');
    END IF;

    IF item->>'status' = 'resolved' THEN
      INSERT INTO public.ticket_status (ticket_id, field, from_value, to_value, changed_by, changed_at)
      VALUES (new_ticket_id, 'status', 'in_progress', 'resolved', support_authors[((ticket_number + 1) % 4) + 1], created_on + interval '16 hours');
    END IF;

    message_total := (item->>'messages')::integer;
    FOR message_number IN 1..message_total LOOP
      support_author := support_authors[((ticket_number + message_number - 1) % 4) + 1];
      INSERT INTO public.ticket_messages (ticket_id, message_text, author, created_at)
      VALUES (
        new_ticket_id,
        CASE message_number
          WHEN 1 THEN format('I am following up on "%s". Please let me know what information you need from our side.', title_text)
          WHEN 2 THEN format('We have begun reviewing "%s" and will update this ticket once we identify the next step.', title_text)
          WHEN 3 THEN 'Thank you. We have added the requested details and can provide logs or screenshots if they would help.'
          WHEN 4 THEN 'We are continuing to investigate and have shared the current findings with the relevant product team.'
          ELSE 'The issue is now resolved on our side. Please confirm that the expected behavior is restored for your team.'
        END,
        CASE WHEN message_number % 3 = 1 THEN item->>'created_by' ELSE support_author END,
        created_on + interval '2 days' + (message_number * interval '3 hours')
      );
    END LOOP;
  END LOOP;
END
$seed$;

COMMIT;

-- Post-load checks
SELECT 'tickets' AS table_name, count(*) AS row_count FROM public.tickets
UNION ALL SELECT 'ticket_messages', count(*) FROM public.ticket_messages
UNION ALL SELECT 'ticket_status', count(*) FROM public.ticket_status;

SELECT t.ticket_id, t.status AS ticket_status, latest.to_value AS latest_logged_status
FROM public.tickets AS t
JOIN LATERAL (
  SELECT ts.to_value
  FROM public.ticket_status AS ts
  WHERE ts.ticket_id = t.ticket_id AND ts.field = 'status'
  ORDER BY ts.changed_at DESC, ts.status_id DESC
  LIMIT 1
) AS latest ON true
WHERE latest.to_value IS DISTINCT FROM t.status;
