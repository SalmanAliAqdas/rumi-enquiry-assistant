# Project status

Updated: 2026-10-28 (Asia/Karachi).

## Private fictional test enquiries

Owner reports that the Vercel/Neon deployment and administrator login work, and
Gemini settings are configured in Vercel. Those are owner-reported facts; this
change does not repeat live provider calls or independently verify cloud hosting.

- The private dashboard now offers **New test enquiry**, opening an authenticated
  fictional-name/email/message form. Its CSRF-protected private API reuses the
  existing `Submission` validation, shared duplicate/save-first storage, processing
  pipeline, and private inbox. After processing, the browser opens the saved detail
  page for review/editing, including when processing fails.
- New private test records use `REA-TEST-` references and visible fictional labels
  in the inbox/detail. Existing records are not rewritten. No schema migration,
  administrator reset, environment change, or email sending is introduced.
- Portfolio mode and public Explore Demo stay in place. Anonymous enquiry creation
  remains blocked in portfolio mode. Private submissions consume the existing
  shared submission allowance and the same local/global Gemini budgets; public
  live-demo enablement does not control this authenticated testing path.
- Duplicate retries return the saved record without another model call. Changed
  input with a reused submission token is rejected. Provider/guard failures leave
  a saved failed enquiry for explicit retry, with no fallback. Existing manual
  draft/status preservation, candidate application, revision checks, and unsaved
  draft guards are reused.

Verified: full pytest with isolated SQLite and localhost PostgreSQL 17.11 databases
over TLS, **189 passed, 1 skipped**. The skip is the PostgreSQL-only schema check's
SQLite parameter. The new checks cover authentication/CSRF, validation, save-first
processing without an open row transaction, duplicate/conflict handling, private
portfolio submission/editing, provider/guard failures, and shared request limits.
The SQLite-only run separately passed **119 tests, 1 skipped**. Ruff lint/format,
dependency check, and `git diff --check` passed.

The updated Chrome smoke passed private dashboard → fictional form → saved review
→ edit/save, plus the existing public/retry/candidate/unsaved-guard workflow. The
Explore Demo browser smoke also passed. Desktop/mobile private-form screenshots
were inspected and remain ignored under `artifacts/`. No browser JavaScript errors
or tested mobile overflow. Providers were mocked/blocked; no live Gemini calls.

Existing local `.env`, private FAQ, administrator/enquiry/session rows, and SQLite
schema fingerprints are preserved. Tests use isolated databases and mocked/blocked
providers. SchoolOS is untouched; no direct Vercel/Neon configuration changes.

## Standalone portfolio preparation (historical)

The separate noncommercial Vercel Hobby / Neon Free portfolio is implemented and
locally verified. It has not been provisioned, built on Vercel, or deployed.
Follow [DEPLOYMENT.md](DEPLOYMENT.md) for exact setup and verification commands.

- PostgreSQL uses psycopg 3 alongside the existing SQLite default. The PostgreSQL
  engine uses NullPool, bounded connections and transaction-local timeouts; it
  never falls back to SQLite. Cloud startup checks the schema and performs no DDL.
- PostgreSQL revision 1 initializes only a fresh empty database via the CLI, with
  transactional DDL, a migration lock, and durable shared-budget rows. Repeated
  initialization preserves data and counters. SQLite revision 3 is an explicit,
  integrity-backed additive migration; existing local data was not migrated here.
- The private CLI prompts without echo for the cloud connection URL, ignores the
  local `.env` in that mode, hashes a new administrator password, and refuses
  administrator replacement and password-echo fallback. No bootstrap HTTP route.
- Vercel configuration selects FastAPI, `app.main:app`, Python 3.13, packaged
  templates/assets/fictional JSON, function duration, and private-file exclusions.
  Portfolio configuration requires PostgreSQL TLS, secure cookies, explicit hosts,
  and shared limits. It forces fictional knowledge and disables arbitrary enquiry
  submissions; the existing local form remains available outside portfolio mode.
- Explore Demo uses hand-authored saved fictional fixtures and clearly identified
  deterministic simulation. Optional live generation accepts only fixed fictional
  samples, saves attempts in a separate table, and cannot retrieve private inbox
  records. CSRF protects form mutations. Existing administrator sessions survive
  visits to Explore Demo. No drafts or messages are sent automatically.
- Shared database request limits cover all instances, independently of forwarded
  IPs and anonymous sessions. Gemini has a persistent UTC-day allowance, a lifetime
  count, and an expiring global lease. Usage is reserved before a call; failures
  consume usage. Guard outages deny admission. Local budgets, manual retry/candidate
  handling, draft revisions, and unsaved-edit guards remain in place. Live public
  generation defaults off; no paid fallback or billing change is implemented.

Verified during this preparation:

- `python -m pytest -q --basetemp=artifacts/pytest-final`, with a localhost
  `TEST_POSTGRES_URL` requiring TLS: **161 passed, 1 skipped**. The one skip is the
  PostgreSQL-specific schema/driver test's SQLite parameter. All PostgreSQL cases
  ran against isolated databases on portable PostgreSQL **17.11**, psycopg **3.3.6**.
  Tests covered both backends' workflow/authentication/revision/candidate behavior,
  shared admission races across engines, restart persistence, global lease/caps,
  explicit migrations, CLI administrator creation, and fictional-data isolation.
- A focused TLS portfolio smoke passed actual PostgreSQL TLS, hidden-URL migration
  and administrator CLI, HTTPS cookies, private login, simulation, and an explicitly
  mocked live demo path with its persistent global cap. No real Gemini call occurred.
- `ruff check .`, `ruff format --check .`, `python -m pip check`, and
  `git diff --check` passed. The original browser workflow and new Explore browser
  check passed; desktop/mobile Explore screenshots were inspected and remain under
  ignored `artifacts/`. No JavaScript errors or tested mobile horizontal overflow.
- A final wheel built and installed into a separate ignored environment with the
  pinned dependencies. An isolated installed-package smoke confirmed templates,
  CSS/JS, fictional data, simulation, private API protection, and psycopg import;
  its dependency check passed. This is a Python packaging check, not a Vercel build.
- Private `.env`/FAQ files and existing administrator/enquiry/session rows and
  SQLite schema fingerprints remained intact during verification. No local data,
  passwords, or knowledge were uploaded. Existing local SQLite remains version 2;
  stop the app and run its documented backed-up v3 migration when adopting this
  source. Unrelated `.vscode/` changes remain outside the commits.

Remaining setup: create a fresh separate Rumi Neon project/database in the existing
account; initialize it and create its unique administrator privately; import this
repository into a new Rumi Vercel project with the documented variables; then
perform the hosting review, deployment, and live verification. SchoolOS and all
existing Neon/Vercel resources are unchanged. No Neon/PgBouncer connection, Vercel
build, cloud cold-start, or live-host checks have run. No new live Gemini requests.

Git delivery: implementation commit `8db7807edbedf33a849c73133a77ef2fc2acd397`
(`Prepare isolated portfolio for Vercel and PostgreSQL`) was pushed to the expected
repository's `main`; `git ls-remote` verified that exact remote SHA. The subsequent
documentation-only delivery commit records this evidence.

[GitHub Actions Checks run 40613364956](https://github.com/SalmanAliAqdas/rumi-enquiry-assistant/actions/runs/40613364956)
completed successfully on implementation commit `8db7807`: Ubuntu/Python 3.13,
disposable PostgreSQL 17 service, pinned installation, editable project install,
dependency check, SQLite/PostgreSQL pytest suite, Ruff lint, and format check.
The temporary local PostgreSQL server was stopped after verification. No cloud
resources or deployment were created by either local checks or this CI run.

## Phase 3 completion (historical)

The agreed small local prototype is implemented across Phases 1–3. Owner approval
of real business knowledge and ongoing manual review remain operational tasks,
not missing application features. No hosting environment was selected or verified.

| State | Phase 3 |
| --- | --- |
| Planned | Finish local usability, private configuration/knowledge status, concrete reliability/security review, regression/browser/clean-install checks, owner documentation, commit/push and CI verification. |
| Implemented | Clear customer-needs/next-step views, separate processing/workflow labels, candidate notices, private setup panel/API, zero-knowledge guidance, saved/unsaved states, duplicate-action guards, revision-checked browser draft saves, local login/model budgets, SQL parameter redaction, pagination bounds, keyboard/mobile improvements, owner guide. |
| Tested | 93 isolated pytest tests passed; Ruff lint/format and pip check passed. Extended Chrome workflow and desktop/mobile inspection passed. Clean pinned installation passed in demo mode without a key. GitHub Actions passed on the completion commit. |
| Committed | `69e869f` — `Complete Phase 3 usability and reliability review`. Final delivery evidence is recorded in a subsequent documentation commit. |
| Pushed | Completion commit `69e869f` pushed to the expected repository's `main`; remote SHA verified. |
| Deployed | Not deployed. Localhost only; no SchoolOS, Vercel, Neon, or billing changes. No deployment-readiness claim. |

### Phase 3 verification scope

Remote CI: [Checks run 40570636020](https://github.com/SalmanAliAqdas/rumi-enquiry-assistant/actions/runs/40570636020)
completed successfully on completion commit `69e869f` (Ubuntu, Python 3.13).

- Normal automated tests and browser checks use temporary databases, fictional
  records, and mocked providers. No real Gemini requests were repeated: its request
  format and model configuration did not change, and the successful live Phase 2
  English/Urdu/Roman Urdu check below is retained as historical evidence.
- Real Chrome workflow passed submission/receipt, login, safe setup status,
  search/filter/pagination, empty state, detail/edit/save/copy, unsaved-edit retry
  guard, mocked processing failure/retry/candidate application, preserved manual
  draft/Reviewed status, logout, and subsequent private API rejection. No JavaScript
  errors. Desktop/mobile screenshots were inspected and stay under ignored artifacts/.
- The browser check found horizontal overflow from absolutely positioned accessible
  link text in the scrolling table. Establishing a containing block on that region
  fixed it; mobile viewport overflow checks now pass.
- A new isolated environment installed the existing 53 pinned dependencies and
  project v0.3.0. It ran a demo submission/receipt, administrator login, status API,
  dashboard, and enquiry detail with no API key or real records. Temporary data was
  cleaned up and its dependency check passed. No runtime dependency changes or
  database column migration were required by Phase 3.
- Local limits are in-memory and shared only within one process: 5 credential
  checks/300 seconds (cleared on successful login), 6 Gemini-mode starts/60 seconds,
  at most 2 active Gemini attempts. Restart resets limits; multiple processes have
  separate budgets. These do not provide distributed production protection.
- Existing API clients may omit expected_revision for compatibility; browser saves
  always include it, and candidate application always enforces its revision.
- Existing private knowledge/approval flags, `.env`, credentials, and local records
  are preserved. Unrelated `.vscode/` work remains outside the intended changes.
- The verified localhost app was restarted with v0.3.0 after confirming no active
  processing. HTTP 200 and its OpenAPI version were checked. Before/after local
  fingerprints matched for `.env`, the private FAQ, enquiries, administrator, and
  session rows. No migration, real-model request, or private-data edit was performed.

| State | Phase 1 delivery (historical) |
| --- | --- |
| Planned | Local form, persistent records, deterministic demo processor, private workflow, security safeguards, tests, documentation, CI. |
| Implemented | Application, CLI, templates/assets, isolated tests, optional browser smoke, example FAQ, documentation, GitHub Actions. |
| Tested | 27 pytest tests passed; Ruff lint and format checks passed; pip dependency check passed. Chrome smoke passed; desktop/mobile screenshots inspected. GitHub Actions also passed on the implementation commit. |
| Committed | Implementation committed as `279420a` with message `Build Phase 1 FastAPI enquiry workflow`. Delivery evidence recorded in a subsequent documentation commit. |
| Pushed | Implementation commit `279420a` successfully pushed to the expected repository's `main` branch; tracking `origin/main`. |
| Deployed | Not deployed. Localhost only; Vercel and Neon unchanged. |

## Phase 2 status

| State | Phase 2 |
| --- | --- |
| Planned | Optional Gemini, validated/grounded output, save-first processing, safe retries, migration, verification. |
| Implemented | Official google-genai adapter, async processor interface, configuration diagnostics, bounded calls, approved-only JSON FAQ loader, source snapshots, sanitized states, atomic claims, attempt history, candidates/revision checks, backed-up migration, review UI, tests and smoke commands. |
| Tested | 83 pytest tests passed, Ruff lint/format and pip check passed. Prior Chrome mocked workflow passed. Real Gemini smoke now passed for English, Urdu, and Roman Urdu after correcting the provider JSON Schema field. |
| Committed | Baseline `0d0249d`; schema correction and live-verification notes: `5fe3a34`, with successful remote Actions verification. |
| Pushed | Implementation SHA verified on the expected remote's `main`; tracking `origin/main`. |
| Deployed | Not deployed; local only. SchoolOS, Vercel, and Neon unchanged. |

Explicit demo mode remains. Gemini mode never silently falls back to demo.
There is no automatic sending, billing activation, paid-model fallback, automatic
provider retry, or continuation. Incoming valid enquiries are saved before processing.

Default model: `gemini-3.5-flash-lite`. Its existence/structured output support was
checked in [model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
and free-tier input/output pricing independently in [official pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite)
on 2026-10-27. Account-specific quota/billing enrollment remains unverified.
The older 2.5 family is restricted to prior users; the selected 3.5 model is
documented for new projects. Minimal thinking is configured for the default model.

**Real Gemini verification: PASSED on 2026-10-28.** With owner-configured Gemini
settings, the explicit smoke command returned valid structured results for all
three fictional English/Urdu/Roman Urdu messages. The initial live call exposed
a provider schema-format error; the adapter now uses `response_json_schema`
instead of the legacy `response_schema` field, with regression coverage of the
serialized wire field. No key, raw provider response, or generated content was
printed. No smoke enquiries were saved or replies sent. This verifies live access
for these requests, not unlimited quota or general language/factual quality.

No owner FAQ was approved. The 13 JSON examples remain false, as does the status
of the existing fictional Markdown FAQ. Approved fixtures are fictional/test-only.
Private owner knowledge belongs in ignored `private/faq.json`.
That file was missing and was created from the example with all 13 entries still
unapproved. Existing `.env` settings and the configured model were preserved.

Migration verification uses temporary populated Phase 1 databases and checks
receipts, exact message whitespace, manual draft, Reviewed status, demo history,
administrator hash/session, backup integrity, and repeatability. No normal local
database was deleted, recreated, or upgraded as part of automated verification.
The existing `.env` was not overwritten. Unrelated `.vscode/` work is preserved.

Remote Phase 2 CI: [Checks run 40563864676](https://github.com/SalmanAliAqdas/rumi-enquiry-assistant/actions/runs/40563864676)
completed successfully on `0d0249d` (Ubuntu, Python 3.13).

To fulfill the subsequent request to start the app, the existing Phase 1 database
was backed up with the integrity-checked SQLite backup API and migrated to version 2.
The backup is under ignored `backups/`; original records and administrator credentials
are preserved. This was a runtime upgrade, separate from isolated automated tests.

## Remaining owner tasks and optional next steps

- Real Gemini smoke verification has passed. Owner approval of actual FAQ facts
  and broader model-quality evaluation remain outstanding.
- Keep the private FAQ accurate, approve verified individual entries, and review
  every draft. Choose local backup/retention practices; no automatic deletion exists.
- Optional future hosting requires a separate review of the chosen environment,
  storage, HTTPS, secrets, distributed protection, privacy, and operations. Nothing
  is deployed or claimed ready for an unspecified host.

See README for the exact local setup and verification commands.

## Verification evidence

- Python 3.13.5 on Windows; compatible application/test versions pinned in `requirements.lock`.
- Tests cover persistence across app restarts, idempotent retry/conflict, invalid
  input, body-size limits, anonymous page/API protection, login failure and CSRF,
  session rotation/expiry/revocation, forged sessions, draft/status persistence,
  search/filter/pagination/counts, HTML escaping, deterministic clarification,
  host checks, and safe CLI administrator creation.
- Real Google Chrome through Playwright: mobile form and receipt, login,
  dashboard filtering, draft edit and reload persistence, logout, private API
  rejection afterward; no JavaScript errors. Temporary database only.
- Desktop (1440px) and mobile (390px) screenshots saved locally under ignored
  `artifacts/`; no passwords or real customer records captured. Form, dashboard,
  and detail rendering inspected; form/detail mobile viewport overflow checks passed.
- No deployment attempted. No changes to SchoolOS, Vercel, or Neon.
- Remote CI: [Checks run 40558489583](https://github.com/SalmanAliAqdas/rumi-enquiry-assistant/actions/runs/40558489583)
  completed successfully on implementation commit `279420a` (Ubuntu, Python 3.13).

## Local handoff

The existing administrator was preserved. The local app was started on
`http://127.0.0.1:8000/` at the owner's request after live verification and migration.
New installations use `python -m app.cli create-admin`. Browser smoke verification
uses discarded random credentials and temporary databases. The local-prototype
limitations in README still apply; no deployment or billing change was made.
