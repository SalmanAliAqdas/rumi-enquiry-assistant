# Project status

Updated: 2026-10-27 (Asia/Karachi).

| State | Phase 1 status |
| --- | --- |
| Planned | Local form, persistent records, deterministic demo processor, private workflow, security safeguards, tests, documentation, CI. |
| Implemented | Application, CLI, templates/assets, isolated tests, optional browser smoke, example FAQ, documentation, GitHub Actions. |
| Tested | 27 pytest tests passed; Ruff lint and format checks passed; pip dependency check passed. Chrome smoke passed; desktop/mobile screenshots inspected. GitHub Actions also passed on the implementation commit. |
| Committed | Implementation committed as `279420a` with message `Build Phase 1 FastAPI enquiry workflow`. Delivery evidence recorded in a subsequent documentation commit. |
| Pushed | Implementation commit `279420a` successfully pushed to the expected repository's `main` branch; tracking `origin/main`. |
| Deployed | Not deployed. Localhost only; Vercel and Neon unchanged. |

## Scope

Phase 1 only. No model connected, no API key, no outgoing replies. Fictional data
only. No actual business policies or commitments included. The admin CLI requires
an explicitly chosen password; no local default account is created automatically.

## Remaining roadmap

- Phase 2 (planned, not implemented): official Google GenAI SDK, Gemini,
  approved FAQ, validated structured output, configurable model, timeouts,
  quota/error handling, and continued manual review. No silent demo fallback.
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

No administrator was created in the normal application database; choose local
credentials with `python -m app.cli create-admin`. Browser verification used
discarded random test credentials and temporary databases. No app server is left
running by the completed smoke check. No implementation issue remains from the
checks performed; the local-prototype limitations in README still apply.
