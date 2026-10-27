# Project status

Updated: 2026-10-27 (Asia/Karachi).

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
| Tested | 83 pytest tests passed (including the original Phase 1 coverage), Ruff lint/format passed, pip check passed. Chrome demo + mocked Gemini failure/retry/candidate workflow passed; screenshots inspected. GitHub Actions passed on the implementation commit. No real model called. |
| Committed | `0d0249d` — `Add Phase 2 Gemini enquiry processing`. Delivery evidence recorded in a subsequent documentation commit. |
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

**Real Gemini verification: NOT RUN.** The explicit smoke command reported that
Gemini mode and a server-side key were not configured. Mocked tests and browser
verification are not evidence of live model access, language quality, or free quota.

No owner FAQ was approved. The 13 JSON examples remain false, as does the status
of the existing fictional Markdown FAQ. Approved fixtures are fictional/test-only.
Private owner knowledge belongs in ignored `private/faq.json`.

Migration verification uses temporary populated Phase 1 databases and checks
receipts, exact message whitespace, manual draft, Reviewed status, demo history,
administrator hash/session, backup integrity, and repeatability. No normal local
database was deleted, recreated, or upgraded as part of automated verification.
The existing `.env` was not overwritten. Unrelated `.vscode/` work is preserved.

Remote Phase 2 CI: [Checks run 40563864676](https://github.com/SalmanAliAqdas/rumi-enquiry-assistant/actions/runs/40563864676)
completed successfully on `0d0249d` (Ubuntu, Python 3.13).

Read-only local schema inspection confirmed an existing Phase 1 database. Its
upgrade remains an explicit owner action: stop the app and run
`python -m app.cli migrate-db` to create the backup and apply the migration.
No normal local records or administrator credentials were changed by verification.

## Remaining roadmap

- Phase 2 implementation is complete; real-model verification awaits explicit
  Gemini configuration and available free quota.
- Phase 3 (planned): further polish, security/reliability checks, CI refinement,
  publishing/documentation completion, optional deployment preparation.

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

No administrator was created in the normal application database. Existing
installations must preserve their administrator and run `python -m app.cli migrate-db`.
New installations use `python -m app.cli create-admin`. Browser verification used
discarded random test credentials and temporary databases. No app server is left
running by the completed smoke check. No implementation issue remains from the
checks performed; the local-prototype limitations in README still apply.
