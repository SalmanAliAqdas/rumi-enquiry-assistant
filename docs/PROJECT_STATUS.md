# Project status

Updated: 2026-10-28 (Asia/Karachi).

## Phase 3 completion

The agreed small local prototype is implemented across Phases 1–3. Owner approval
of real business knowledge and ongoing manual review remain operational tasks,
not missing application features. No hosting environment was selected or verified.

| State | Phase 3 |
| --- | --- |
| Planned | Finish local usability, private configuration/knowledge status, concrete reliability/security review, regression/browser/clean-install checks, owner documentation, commit/push and CI verification. |
| Implemented | Clear customer-needs/next-step views, separate processing/workflow labels, candidate notices, private setup panel/API, zero-knowledge guidance, saved/unsaved states, duplicate-action guards, revision-checked browser draft saves, local login/model budgets, SQL parameter redaction, pagination bounds, keyboard/mobile improvements, owner guide. |
| Tested | 93 isolated pytest tests passed; Ruff lint/format and pip check passed. Extended Chrome workflow and desktop/mobile inspection passed. Clean pinned installation passed in demo mode without a key, with temporary records and credentials. |
| Committed | Pending final diff review; requested message: `Complete Phase 3 usability and reliability review`. |
| Pushed | Pending Phase 3 publication and remote SHA/Actions verification. |
| Deployed | Not deployed. Localhost only; no SchoolOS, Vercel, Neon, or billing changes. No deployment-readiness claim. |

### Phase 3 verification scope

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
