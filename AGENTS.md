# Project guidance

- Phase 1 is local only: FastAPI, SQLModel/SQLite, Jinja2, deterministic demo processing.
- Keep code readable for learners. No external model calls or invented business commitments.
- Work only in this project. Do not change SchoolOS, Vercel, or Neon.
- Protect private pages and APIs; require CSRF for cookie-authenticated mutations.
- Keep credentials, databases, exports, environment files, and virtual environments out of Git.
- Use temporary databases in tests. Run `python -m pytest`, `ruff check .`, and
  `ruff format --check .` before committing.
- Preserve original messages except trimming leading/trailing whitespace. Never use HTML `safe`.
- Update docs/PROJECT_STATUS.md with verified facts. Never claim a push or deployment unverified.
