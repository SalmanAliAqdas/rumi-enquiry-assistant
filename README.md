# Rumi Enquiry Assistant

A local FastAPI application that saves software-service enquiries and prepares
private reply drafts for a single administrator reviewing software-service
enquiries. Phases 1–3 implement the agreed local prototype, including optional
Gemini through the official `google-genai` SDK. Explicit demo mode needs no API
key. No replies are sent automatically. Hosting is a separate optional next step.

## Implemented features

- Validated public form, SQLite persistence, receipt references, idempotent retries.
- Save-first processing: model failures preserve the enquiry and public receipt.
- Explicit demo/Gemini modes, bounded structured output, approved FAQ sources,
  clarification questions, English drafts, and sanitized private diagnostics.
- Private dashboard with search, category/status filters, pagination, counts,
  editable drafts, source snapshots, and processing history.
- Authenticated/CSRF-protected retry and candidate application, preserving manual
  drafts and Reviewed/Closed workflow statuses through processing.
- Argon2 passwords, expiring/revocable server-side sessions, CSRF, escaped HTML,
  localhost binding, and request-size limits.
- Backed-up Phase 1 migration, isolated tests, browser checks, and GitHub Actions.
- Private setup/knowledge status, suggested next steps, visible unsaved state,
  revision-checked browser saves, accessible controls, and per-process local limits.

## Upgrade an existing installation (PowerShell)

Run from the repository root. Stop the app first. **Preserve `.env` and the
database; do not recreate the administrator.**

```powershell
.\.venv\Scripts\python -m pip install -r requirements.lock
.\.venv\Scripts\python -m pip install --no-deps -e ".[dev]"
.\.venv\Scripts\python -m app.cli migrate-db
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --reload
```

`migrate-db` uses the configured `DATABASE_URL`. It first creates a uniquely named,
integrity-checked SQLite backup under ignored `backups/`, including committed WAL
data. An explicit transaction adds columns and the processing-attempt table,
preserving receipts, messages, drafts, categories, workflow/processing statuses,
timestamps, administrator hashes, and sessions. It is safe to repeat; each run
makes a distinct backup. New databases need no previous-data backup.

Startup refuses a Phase 1 schema until migration. `create_all` does not substitute
for column migration. Backups contain private data and password hashes. For
rollback, stop the app, preserve the upgraded file separately, and restore a
verified backup with the matching Phase 1 application version. Never overwrite
a live SQLite file.

Phase 3 adds no database columns or new runtime dependencies. An installation
already migrated for Phase 2 needs only the updated source and an application
restart; preserve its `.env`, private FAQ, database, and administrator. Running
`migrate-db` again is optional and makes another backup.

## First installation

Python 3.13 is verified; Python 3.11+ is required. From a clone's root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.lock
.\.venv\Scripts\python -m pip install --no-deps -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python -m app.cli create-admin
```

Copy `.env.example` only when `.env` does not already exist. The CLI prompts for a
username and hidden, confirmed password (12–256 characters). It stores an Argon2
hash and refuses to replace an existing administrator. No default account exists.
Virtual environment activation is optional.

`requirements.lock` pins the application/test dependency closure verified on
Windows/Python 3.13. Browser dependencies are an optional extra. For deliberate
upgrades, install `-e ".[dev]"` in a fresh environment, run checks, and regenerate pins.

## Configuration

Pydantic Settings reads environment variables and the existing `.env`. Update
individual settings without replacing the file. Safe defaults:

```dotenv
DATABASE_URL=sqlite:///./data/rumi.db
COOKIE_SECURE=false
SESSION_MINUTES=60
PROCESSOR_MODE=demo
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite
AI_TIMEOUT_SECONDS=20
AI_MAX_OUTPUT_TOKENS=1200
FAQ_PATH=private/faq.json
```

To opt in, set `PROCESSOR_MODE=gemini` and enter your key locally as
`GEMINI_API_KEY=<your-server-side-key>`. Keep it out of Git, commands, frontend
assets, prompts, and screenshots. The app represents it as a Pydantic secret and
never returns it. Restart after configuration changes.

AI timeout must be 1–60 seconds; output budget 256–2000 tokens. The processor
factory validates AI-only settings so missing/invalid AI configuration cannot
prevent valid enquiries being saved. Failures appear privately. Invalid database
or session settings remain startup errors. Only local SQLite is supported.

`COOKIE_SECURE=false` permits HTTP localhost; future HTTPS hosting must use true.
Session lifetime is absolute (`SESSION_MINUTES`, 1–1440); activity does not extend
it. Use one hostname consistently because localhost/127.0.0.1 cookies differ.

### Model and free-tier verification

Default: **`gemini-3.5-flash-lite`**. Model existence/structured-output support and
free-tier pricing were checked separately on 2026-10-27:

- [Official model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
- [Official pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite)
- [Project-specific rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

Standard input/output are listed as free of charge on the free tier. This does
not verify an individual project's available quota. Check the project's free-tier
status and active limits in AI Studio. The app cannot determine billing enrollment
from a key; use a project without billing. Free-tier content may be used to improve
Google's products: use fictional messages while evaluating this prototype.

The 2.5 family is restricted to existing users; 3.5 Flash-Lite is recommended for
new projects. The adapter uses its documented minimal thinking level to leave
more of the conservative output budget for the structured answer.

No billing activation, alternate-model routing, paid fallback, grounding tools,
SDK retries, or automatic continuation is used. Request storage/logging is disabled
in the generation config. The model is configurable; verify its pricing and
availability before changing it.

## Approve owner knowledge

`docs/faq.example.json` contains **13 fictional examples, all `approved=false`**.
`docs/EXAMPLE_FAQ.md` stays fictional and unapproved. Neither becomes RumiWare
policy. Approved test fixtures are fictional and used only for verification.

On first configuration, create a private file without overwriting existing knowledge:

```powershell
New-Item -ItemType Directory -Force private
if (-not (Test-Path private/faq.json)) {
    Copy-Item docs/faq.example.json private/faq.json
}
```

The file is a JSON array of entries in this format:

```json
{
  "id": "owner-chosen-id",
  "question": "A question reviewed by the owner",
  "answer": "Replace with verified owner-approved facts in English.",
  "approved": false
}
```

Review and replace each example. Set `approved: true` only for explicitly approved
real answers. Write approved answers in English for the initial English-draft
workflow; keep uncertain entries false. Do not approve placeholders in bulk.

Only explicit JSON boolean approvals are loaded. IDs must be unique and use
letters/numbers/hyphens/underscores. Limits: 100 entries, 100 KB file, 60-character
IDs, 300-character questions, 1500-character answers. Knowledge reloads per attempt.
Private knowledge, databases, backups, exports, `.env`, and screenshots are ignored.

Gemini returns category, summary, proposed draft, up to three questions, approved
FAQ IDs, `needs_clarification`, and `review_reason`. Pydantic validates lengths,
enums, fields, and source IDs. Unknown fields/confidence percentages are rejected.

Schema validation cannot establish factual grounding. The proposed draft is
validated, but the saved reply's business facts are deliberately rendered from
the exact cited approved answers, with a neutral English acknowledgement and
review notice. Questions are shown separately. No applicable cited source means
a neutral clarification/handoff draft and a human-review reason. This occurs
only after valid model analysis; a failed model call never becomes demo output
or a fake success. Oversized composed drafts are rejected.

Source snapshots show what was approved at generation time. They are historical
evidence; review old candidates against current owner knowledge before applying them.

See [the owner guide](docs/OWNER_GUIDE.md) for approving individual verified facts,
testing a question, the daily review workflow, troubleshooting, and safe recovery.

## Run and review

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --reload
```

- Form: <http://127.0.0.1:8000/>
- Login: <http://127.0.0.1:8000/admin/login>
- Dashboard: <http://127.0.0.1:8000/admin>
- API docs: <http://127.0.0.1:8000/docs>

Demo mode visibly states **“Demo processing — no AI model connected.”** Keyword
matching handles website/mobile/automation categories and requests clarification
for unknown/multiple matches. Gemini mode is labelled and the form discloses that
the message is sent to Google. Separate name/email fields are not sent; personal
information written inside the message is still part of that message.

Processing states (`Pending`, `Processing`, `Completed`, `Failed`) are separate
from workflow (`New`, `Reviewed`, `Closed`). Completed does not mean approved.
Private diagnostics distinguish configuration/key/FAQ problems, authentication,
model availability, quota, timeout, provider failures, blocked/empty/truncated
responses, invalid output/sources, and interrupted attempts. Only fixed sanitized
messages are stored; raw exceptions/provider responses are not logged or exposed.

Authenticated, CSRF-protected retry accepts Failed/Pending records and Processing
claims interrupted for over 90 seconds. It uses the current server configuration.
Mode changes require explicit configuration; no automatic fallback occurs.
Completed records cannot be retried through this action.

Successful retries create separate candidates and preserve the saved draft and
workflow. Save unsaved edits, inspect questions and sources, then explicitly use
**Apply candidate to saved draft** if appropriate. This replaces generated fields
and draft, keeps workflow status, and checks candidate identity/draft revision to
reject stale applications. First submissions populate an initial draft only if
no administrator edited it or changed workflow while processing. Replies stay drafts.

## Data flow and API

Browser → Pydantic → committed original enquiry → short atomic processing claim →
bounded processor call with no open database transaction → saved result/failure →
minimal public receipt. Duplicate submission keys do not repeat processing.

| Route | Access / behavior |
| --- | --- |
| `POST /api/enquiries` | Public; name/email/message/UUID submission_key; receipt only. |
| `GET /api/admin/enquiries` | Admin; q/category/status/page/page_size filters. |
| `GET /api/admin/enquiries/{id}` | Admin; private fields, diagnostic, candidate. |
| `PATCH /api/admin/enquiries/{id}` | Admin + CSRF; reply_draft/workflow_status, optional expected_revision. |
| `GET /api/admin/status` | Admin; safe setup metadata, key presence only, approved count. |
| `POST /api/admin/enquiries/{id}/retry` | Admin + CSRF; retry eligible processing. |
| `POST /api/admin/enquiries/{id}/apply-candidate` | Admin + CSRF; candidate_id/draft_revision. |
| `POST /admin/login`, `POST /admin/logout` | Form CSRF; rotation/revocation. |

The form keeps one UUID across network retries. Reusing it with different validated
content returns 409. There is no public enquiry lookup. Boundary whitespace is
trimmed; internal message spaces/newlines are preserved separately from generated
fields. Email validation may normalize the domain. All timestamps are UTC; private
API values have an explicit UTC offset. SQLite stores timezone-naive UTC.

Private APIs use the session cookie and `X-CSRF-Token` from authenticated page
metadata. The cookie is HttpOnly, SameSite=Strict, and expiring; the database stores
only a hash of its opaque ID. Anonymous APIs return 401; protected HTML redirects
to login. Jinja2 escapes customer and generated content.

Page numbers are bounded to 1–1,000,000; page sizes to 1–50. The UI offers 5, 10,
25, or 50 records per page and retains filters in previous/next links.

Browser draft saves include `expected_revision`; stale saves fail with 409 and
preserve editor contents. API clients that omit it retain explicit last-write
semantics for compatibility. Candidate application always checks its revision.

The private setup panel shows only safe metadata and advice. It never returns the
key, raw environment, provider errors, or private filesystem paths. SQL exception
parameters are hidden. Use `--no-access-log` when running Uvicorn so private search
queries do not enter access logs. Application code does not log enquiry text.

Local safeguards limit credential checks to 5 per 5 minutes (reset on successful
login), and Gemini-mode processing to 6 starts per minute with 2 active attempts.
These shared in-memory budgets apply only to one process, reset on restart, and
are not distributed production protection. Public submissions still persist and
return receipts when model processing is locally limited. Read the owner guide
for scope and recovery steps.

The model receives only the message and approved FAQ entries, under instructions
treating customer content as untrusted data. It has no tools, secret values,
customer directory, or database access. Schemas/prompts do not guarantee semantic
correctness; all output still requires human review.

## Verification

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\ruff check .
.\.venv\Scripts\ruff format --check .
.\.venv\Scripts\python -m pip check
```

Tests/CI use temporary databases and mocked providers with no API key. An autouse
fixture blocks live SDK model methods; a transport test runs the real SDK serializer
against mock HTTP. Migration tests use populated Phase 1 records/admin/session.
GitHub Actions runs pytest, Ruff, and dependency checks on Ubuntu/Python 3.13.

Optional browser check (installed Google Chrome required):

```powershell
.\.venv\Scripts\python -m pip install -e ".[browser]"
.\.venv\Scripts\python -m scripts.browser_smoke
```

This retains the demo workflow and adds mocked quota failure, retry, candidate
review/application, search/filter/pagination, empty states, clipboard, keyboard
skip navigation, and manual-draft/status preservation. It uses temporary data
and random credentials, saves fictional screenshots to ignored `artifacts/`, and
stops its localhost server afterward. It never calls a real model.

Explicit **real Gemini** verification:

```powershell
.\.venv\Scripts\python -m scripts.gemini_smoke
```

This sends up to three fictional English/Urdu/Roman Urdu messages only when Gemini
mode and a key are explicitly configured. Otherwise it reports NOT RUN. It stops
at the first failure without retries, prints no key/generated content, saves no
enquiries, and sends no replies. Mock success does not verify live model access
or free quota. Actual results are recorded in `docs/PROJECT_STATUS.md`.

## Structure and limitations

`main.py` configures the factory; config/db/models/schemas handle settings and
persistence. `services.py` defines the async processor/demo; `gemini.py` isolates
the provider; `knowledge.py` loads approved facts; `processing.py` coordinates
claims/results/history. Routes, auth, CLI/migration, templates/static assets,
tests, and verification scripts remain separate.

This is a local single-admin prototype with request-based processing, no worker
queue. First submission waits up to the processing timeout. Disconnect/restart
can interrupt processing after saving; an admin must recover it. Claims protect
one enquiry; the additional local budget bounds process-wide Gemini starts and
concurrency but does not establish available provider quota. No background automatic retry
or reprocessing of completed records occurs.

There is no email delivery, password recovery UI, retention tooling, distributed
rate limiting, multi-user permissions, or deployment setup. Protect the local
account/disk. Evaluate real-model language understanding and source relevance;
verify summaries, questions, applicability of approved facts, and every reply.

Phase 3 completes the agreed local prototype's usability/reliability review,
regression coverage, and owner documentation. Business knowledge approval and
ongoing human review remain owner responsibilities. Optional online hosting is a
separate next step requiring review of the chosen environment; deployment
readiness is not claimed. SchoolOS, Vercel, Neon, and billing are not modified.

References: [Google quickstart](https://ai.google.dev/gemini-api/docs/quickstart),
[structured output](https://ai.google.dev/gemini-api/docs/structured-output),
[official SDK](https://googleapis.github.io/python-genai/).
