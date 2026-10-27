# Rumi Enquiry Assistant

A local FastAPI learning prototype that saves software-service enquiries and
prepares deterministic reply drafts for private review.

**Demo processing — no AI model connected.** No API key is needed. No messages,
emails, or model requests are sent. Use clearly fictional data only.

## Phase 1 features

- Public enquiry form with validated name, email, and a 20–3000-character message.
- Receipt reference, submission feedback, and idempotent retries to prevent accidental duplicates.
- SQLite persistence with separate original message, category, summary, draft,
  processing mode/status, workflow status, and UTC timestamps.
- Deterministic keyword matching for Website, Mobile application, Automation, and
  Other / needs clarification. Multiple categories or unknown keywords request clarification.
- Single administrator, Argon2 password hashing, expiring opaque server-side
  sessions, session rotation on login, revocation on logout, and CSRF protection.
- Private dashboard and API with search, category/status filters, pagination,
  workflow counts, original enquiry details, editable drafts, and a copy button.
- Responsive Jinja2 interface, escaped content, local assets, and automated checks.

There is no default administrator or working default password.

## Requirements and setup (PowerShell)

Python 3.13 is the verified version; the source supports Python 3.11 or newer.
Run all commands from the project folder. The commands below call the virtual
environment directly, so PowerShell activation or an execution-policy change is unnecessary.

```powershell
Set-Location 'C:\Users\SALMAN\Downloads\Rumi Enquiry Assistant'
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.lock
.\.venv\Scripts\python -m pip install --no-deps -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python -m app.cli create-admin
```

Copy the environment example only on first setup; preserve an existing `.env`.
The CLI prompts for a username and a hidden, confirmed password of 12–256
characters. It stores an Argon2 hash in SQLite and refuses to replace an existing
administrator. No password is placed in a command, frontend asset, or environment file.

`requirements.lock` pins the complete application/test dependency set used for
verification. For deliberate dependency upgrades, install `-e ".[dev]"` in a fresh
environment, run the checks, and regenerate the pins. The optional browser extra
is separate from the normal dependency lock.

## Configuration

Pydantic Settings reads environment variables and optional `.env` values.

| Setting | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./data/rumi.db` | Local SQLite only; parent directory is created automatically. |
| `COOKIE_SECURE` | `false` | Required for HTTP localhost; a future HTTPS deployment must use `true`. |
| `SESSION_MINUTES` | `60` | Absolute session lifetime, from 1 to 1440 minutes; activity does not extend it. |

All commands use the same database setting. Database files, `.env`, virtual
environments, private exports, and browser artifacts are ignored by Git.

## Run locally

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- Form: <http://127.0.0.1:8000/>
- Admin login: <http://127.0.0.1:8000/admin/login>
- Private dashboard: <http://127.0.0.1:8000/admin>
- API documentation: <http://127.0.0.1:8000/docs>

Use the same hostname consistently: cookies for `localhost` and `127.0.0.1` are
separate. Keep the server bound to localhost. Stop it with Ctrl+C.

## API overview

| Method / route | Access / behavior |
| --- | --- |
| `POST /api/enquiries` | Public; validates and saves an enquiry, returns only a receipt reference/message. |
| `GET /api/admin/enquiries` | Admin; `q`, `category`, `status`, `page`, and `page_size` filters. |
| `GET /api/admin/enquiries/{id}` | Admin; private enquiry detail. |
| `PATCH /api/admin/enquiries/{id}` | Admin + CSRF; edits `reply_draft` and `workflow_status`. |
| `POST /admin/login` | Pre-login session + form CSRF token; rotates session on successful login. |
| `POST /admin/logout` | Admin + CSRF; deletes the session and cookie. |

Public JSON submissions contain `name`, `email`, `message`, and `submission_key`
(a newly generated UUID). The form generates this key. Retrying the same key and
same validated fields returns the same receipt; reusing the key for different
content returns 409. There is no public enquiry lookup. A reference is not a credential.

Names, email, and messages are trimmed at their boundaries. Internal message
whitespace and line breaks are preserved exactly; the summary is a separate
whitespace-normalized excerpt. Email validation may normalize the domain.
Private timestamps are returned as ISO 8601 UTC. SQLite stores them without a
timezone marker; the application always interprets these values as UTC.

The allowed workflow values are `New`, `Reviewed`, and `Closed`; an administrator
can move between them. Generated drafts never imply approval or automatic sending.

Private API calls use the cookie established by form login. Mutations also
require `X-CSRF-Token`, available in the authenticated page's `csrf-token` meta
tag (logout uses a hidden form field). The session cookie is HttpOnly,
SameSite=Strict, and expires after the configured absolute lifetime. Only a hash
of its random identifier is stored in the database. Credentials never enter API
responses. Private API requests return 401 when unauthorized; protected HTML
pages redirect to login.

## Checks

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\ruff check .
.\.venv\Scripts\ruff format --check .
.\.venv\Scripts\python -m pip check
```

Tests create isolated temporary SQLite files and random test credentials. They
do not use local enquiry records or any model service. GitHub Actions runs pytest
and Ruff using Python 3.13 on pushes and pull requests.

Optional real-browser smoke check (requires installed Google Chrome):

```powershell
.\.venv\Scripts\python -m pip install -e ".[browser]"
.\.venv\Scripts\python -m scripts.browser_smoke
```

This starts a temporary localhost server with an isolated temporary database,
checks a full browser workflow at desktop/mobile sizes, and saves fictional-data
screenshots to ignored `artifacts/`. It stops its server afterward. Browser
automation does not create an administrator in your application database.

## Request flow and structure

The browser sends JSON to a public route. Pydantic validates and trims the input.
The route calls the replaceable `Processor` interface, and `DemoProcessor`
returns keyword-based fields. SQLModel saves the original and generated fields
in SQLite; the public route returns a receipt only. Private routes verify the
session before reading records; updates verify CSRF, validate the draft/status,
and commit the changes. Jinja2 escapes all values rendered into HTML.

```text
app/
  main.py, config.py           Application factory, lifespan, settings, safeguards
  db.py, models.py, schemas.py Persistence and validation
  public.py, private.py        Public/private routes
  auth.py, cli.py              Sessions, CSRF, password hashing, admin creation
  services.py                 Replaceable processor interface and demo implementation
  templates/, static/         HTML, CSS, minimal JavaScript
tests/                        Isolated API, security, workflow, and CLI tests
scripts/browser_smoke.py       Optional real-browser verification
docs/EXAMPLE_FAQ.md            Fictional examples, not approved business content
docs/PROJECT_STATUS.md         Implementation and delivery evidence
```

## Limitations and planned work

Phase 1 is a single-admin local prototype. It has no email delivery, public
receipt lookup, password recovery UI, distributed rate limiting, database
migrations, multi-user permissions, retention tooling, or deployment setup.
SQLite and its password hashes are local files: protect the Windows account and
disk. Re-running the CLI will not reset an existing administrator.

Keyword matching is intentionally limited and can miss context or negation.
Summary text is only an excerpt. No actual prices, delivery commitments, client
names, contact details, or business policies are supplied. Example FAQ content is
fictional and needs review before any business use.

Phase 2 is planned: Gemini through the then-current official Google GenAI SDK,
approved FAQ content, validated structured output, configurable model selection,
timeouts, quota/error handling, and manual review. Failed model processing must
be visible and must never silently become a demo answer.

Phase 3 is planned: further UI polish and security/reliability review, CI
refinement, documentation, publishing, and optional deployment preparation.
Basic documentation and CI are already included in Phase 1. Vercel and Neon are
not configured or modified.

Implementation references: [FastAPI password hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/),
[SQLModel session dependencies](https://sqlmodel.tiangolo.com/tutorial/fastapi/session-with-dependency/),
and [Starlette TestClient](https://starlette.dev/testclient/).
