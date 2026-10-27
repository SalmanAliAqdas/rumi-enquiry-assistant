# Owner guide

Rumi Enquiry Assistant is a local review inbox for one administrator. It saves
enquiries, analyzes them in explicit demo or Gemini mode, and prepares drafts.
It does not send messages, approve replies, or decide company policy.

## Add verified knowledge

1. Open your existing private FAQ JSON file in a text editor. Its configured
   location is in your local `.env`; the default is `private/faq.json`. Do not
   replace an existing file with the example.
2. Add a unique, stable ID and a clear question. Write the answer in English
   using facts you have personally verified and have permission to disclose to
   customers and the model provider. Avoid secrets and customer information.
3. Leave `approved` false while drafting. Check prices, scope, terms, contacts,
   qualifications, and commitments against authoritative business records. If
   uncertain, keep the entry unapproved rather than filling gaps with guesses.
4. Set that entry's `approved` value to the JSON boolean `true` only after review.
   Approve individual real facts; never approve all fictional examples in bulk.
5. Save valid JSON and refresh the private dashboard. Expand **Processing setup**
   to check the approved count. FAQ edits reload per attempt; no restart is needed.

The 13 shipped examples are fictional and unapproved. The application never
changes approval flags. Missing/malformed knowledge shows a private setup note;
no raw error or private file path appears in the browser. Only approved entries
are sent to Gemini. Their text snapshots are stored with generated results for review.

## Test a question against your facts

With Gemini intentionally configured, submit one fictional enquiry that asks a
question answered by a newly approved entry. Use `example.com` contact details,
not a customer's identity. Open the receipt's corresponding enquiry in the
private inbox. Check the category, summary, questions, source IDs, and saved draft.
The factual draft text should match applicable approved answers. Also try a
fictional question you have not answered: it should ask for clarification or
human handoff rather than inventing business details.

This is a deliberate live test and uses provider quota. Ordinary pytest and
browser checks are mocked and do not verify live answer quality. Demo mode uses
keyword matching/fixed examples and does not test your business knowledge.

If an entry becomes outdated, change or unapprove it. Existing source snapshots
and completed replies are not automatically rewritten. Check older drafts and
candidates against current facts before using them.

## Daily review workflow

1. Open `/admin`, sign in, and check **Processing setup**. It shows mode, configured
   model, key presence (yes/no), approved FAQ count, and setup advice.
2. Search the inbox, filter category/workflow, and use page controls. Counts cover
   all enquiries; the table shows the filtered results. On narrow screens, scroll
   the result region sideways with touch or keyboard to reach every column.
3. Open a record. Read the original message and summary. Processing status is
   independent of New/Reviewed/Closed. **Completed** means analysis finished;
   nothing has been approved or sent. Follow the suggested next step.
4. Review the questions and applicable approved sources. Write/edit the saved
   draft and save it. The browser labels unsaved edits and warns before leaving.
   A stale browser save returns a conflict instead of overwriting a newer draft.
5. If processing failed, read the diagnostic before retrying. Pending records can
   also be retried. Wait 90 seconds before recovering an interrupted Processing
   attempt. A successful retry creates a separate candidate, preserving your
   manual reply and workflow. Inspect it, then explicitly apply it if appropriate.
   Applying replaces generated fields and draft; workflow stays unchanged.
6. Mark the enquiry Reviewed after your review. **Copy current draft** copies the
   text currently in the editor, including unsaved edits if present. Copying does
   not save, send, or change status. Handle any eventual sending outside this app.
   Mark Closed when the review workflow is finished, and sign out when done.

Every reply still needs human review: the model may misunderstand a message,
choose an irrelevant source, or ask an unsuitable question. Approved sources
prove what text was allowed, not that its use fits this customer's situation.
The app deliberately renders factual reply content from cited approved answers,
rather than trusting arbitrary generated business claims.

## Troubleshooting

| Symptom | Next step |
| --- | --- |
| Key configured: No / configuration diagnostic | Check server-side `.env` mode, key, model, timeout, and output limits; restart. Never paste the key into a browser or issue. |
| Zero approved FAQs | Review verified entries. Analysis can still work, but unsupported business questions need handoff. |
| Missing/invalid FAQ | Repair the private JSON file, IDs, boolean approvals, and size limits; refresh setup status. |
| Local sign-in limit | Wait for the 5-minute window. This limit covers all login sessions in one process; new cookies or IP headers do not bypass it. |
| Local processing limit | Wait at least one minute before manually retrying. Original enquiries and drafts remain saved. |
| Local processing busy | Two Gemini-mode attempts are active; wait for one to finish before retrying. |
| Provider quota/rate limit | Check AI Studio and wait. Do not enable billing or change to paid models as a workaround. |
| Timeout/provider failure | Review the original record and retry manually if appropriate. There is no automatic retry/fallback. |
| Blocked, empty, truncated, invalid output/source | Review manually; check configured budget or knowledge as suggested. No invalid result is applied. |
| Stale draft/candidate conflict | Copy your unsaved work, reload, and compare with the saved draft before saving/applying again. |
| Session expired / CSRF error | Keep a copy of unsaved edits, sign in again, and reload the review page. |
| Clipboard unavailable | The app selects the draft. Use Ctrl+C (Command+C on macOS). |

## Local safeguard scope

Each application process permits 5 credential checks in a rolling 300-second
window; a successful login clears that process's login history. Invalid CSRF is
rejected before consuming a credential check. The budget is shared across
sessions/IPs for this single-admin prototype.

Gemini mode permits 6 processing starts in a rolling 60-second window and at most
2 active attempts. Failures can consume starts; requests rejected by the local
gate do not contact the provider. Public submission still saves the enquiry and
returns a receipt; an administrator sees the local-limit diagnostic and can retry.
Duplicate submission keys and ineligible retries do not consume new starts.
Demo mode does not consume the Gemini budget.

These are in-memory, per-process safeguards. Restarting resets them, and multiple
workers each have separate budgets. They are not distributed protection or a
provider quota/billing guarantee. Keep the app bound to localhost with one worker.
The explicit developer live-smoke command is separate from the application budget.

## Backup and recovery

Stop the app before making operational changes. The existing `python -m app.cli
migrate-db` command creates an integrity-checked backup under ignored `backups/`
and ensures schema version 2. Running it on the current schema is safe and makes
a fresh backup. No Phase 3 column migration is needed.

Preserve `.env` and the private FAQ separately in protected local storage; they
are not included in SQLite backups. SQLite backups include enquiries, sessions,
and administrator password hashes: treat them as confidential.

To recover, keep the current database and any journal/WAL sidecars intact. Copy a
chosen verified backup to a **new** database filename while the app is stopped,
point `DATABASE_URL` at that restored file, and run the matching application/schema
migration before starting. Check records and administrator access. Preserve the
original files until recovery is verified; do not delete/recreate the administrator.
There are no automatic retention/deletion jobs. The owner must choose backup,
retention, and secure-disposal practices.

## Optional future hosting

The agreed local prototype is complete. Hosting remains optional and is not
configured or verified. Choose a hosting environment before reviewing persistent
storage, SQLite suitability, HTTPS/Secure cookies, secret management, proxy/host
trust, distributed limits, backups, monitoring, and data/privacy requirements.
No deployment readiness is claimed and no Vercel/Neon/billing changes are required
for local use.
