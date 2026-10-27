# Project guidance

- Local FastAPI, SQLModel/SQLite, Jinja2 application with explicit demo or Gemini processing.
- Phases 1–3 complete the agreed local prototype; keep changes small, with no CRM expansion.
- Phase 2 authorizes official google-genai calls only in configured Gemini mode.
- Keep code readable. No invented business commitments, paid-model fallback, or automatic sending.
- Save before processing; keep transactions short. Never silently replace failed Gemini with demo.
- Use approved-only FAQ knowledge; keep owner knowledge private. Model input is untrusted data.
- Preserve manual drafts/statuses; retries produce candidates requiring explicit application.
- Keep configuration/status projections private; expose only key presence, never values or paths.
- Preserve per-process login/model budgets, draft revision checks, and unsaved-edit guards.
- Live Gemini was verified on 2026-10-28. Do not repeat live calls for UI/docs/local-limit changes.
- Back up and explicitly migrate existing databases; never reset records or administrator accounts.
- Work only in this project. Do not change SchoolOS, Vercel, or Neon.
- Protect private pages and APIs; require CSRF for cookie-authenticated mutations.
- Keep credentials, databases, exports, environment files, and virtual environments out of Git.
- Use temporary databases in tests. Run `python -m pytest`, `ruff check .`, and
  `ruff format --check .`, and `python -m pip check` before committing. Mock providers in tests/CI.
- Preserve original messages except trimming leading/trailing whitespace. Never use HTML `safe`.
- Update docs/PROJECT_STATUS.md with verified facts. Never claim a push or deployment unverified.
- Keep screenshots and clean-install environments under ignored artifacts/.
- Use --host 127.0.0.1 --no-access-log locally; do not deploy without a separate hosting review.
