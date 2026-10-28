# Standalone fictional portfolio: Vercel Hobby and Neon Free

Prepared 2026-10-28. This is a personal, noncommercial demonstration, with no sales,
quotes, payments, or automatic sending. Preparation does not provision or deploy.
Use the existing GitHub repository `SalmanAliAqdas/rumi-enquiry-assistant` and your
existing Vercel/Neon accounts. Create separate Rumi resources when you later deploy;
do not select, change, link, or reuse SchoolOS projects, databases, branches, or secrets.

Official references checked during preparation:

- [Vercel FastAPI entrypoint, dependencies, assets, and lifespan](https://vercel.com/docs/frameworks/backend/fastapi)
- [Python runtime](https://vercel.com/docs/functions/runtimes/python)
- [Hobby personal/noncommercial restrictions](https://vercel.com/docs/plans/hobby)
- [Neon SQLAlchemy](https://neon.com/docs/guides/sqlalchemy)
- [Neon pooled connections](https://neon.com/docs/connect/connection-pooling)
- [Neon connection steps](https://neon.com/docs/connect/connect-from-any-app)

## 1. Create the separate Neon project (later, manually)

1. Sign into the existing Neon account. Verify the Free plan and current quota in
   the console; no upgrade or payment method is needed for this procedure.
2. Create a **new project** named `rumi-portfolio-demo`, in a region close to the
   Vercel function region you intend to use. Do not select an existing SchoolOS project.
3. In that project, use a fresh empty database named `rumi_demo` on its production
   branch, and a role belonging only to this project. No SQLite import or data transfer.
4. Select **Connect**, the correct project/branch/database/role, and Python/SQLAlchemy.
   Obtain both the **direct** URL and the **pooled** URL. The pooled hostname contains
   `-pooler`. Preserve `sslmode=require` and `channel_binding=require` if provided.
   Both `postgresql://` and `postgresql+psycopg://` are accepted; the app uses psycopg 3.
5. Use the direct URL for the private initialization commands below; use the pooled
   URL for Vercel `DATABASE_URL`. Never commit either URL, paste it into an issue,
   shell argument, screenshot, or this repository's `.env`.

The app uses SQLAlchemy NullPool (no idle pool per function), a ten-second connect
timeout, transaction-local statement/lock timeouts, and disabled automatic prepared
statements. Transactions finish before model calls. New connections handle Neon
sleep/resume without retaining stale sockets. Connection failures remain failures;
there is no SQLite fallback.

## 2. Required Vercel environment variables

Enter these in the **new Rumi project's** Settings → Environment Variables for
Production. Use separate empty Neon databases and separate budgets for Preview,
or leave Preview without database credentials and accept that it cannot run.
Never share the production database with untrusted preview code.

| Variable | Portfolio value |
| --- | --- |
| `DATABASE_URL` | New Rumi Neon **pooled** connection URL, with TLS parameters; mark sensitive |
| `PORTFOLIO_MODE` | `true` |
| `COOKIE_SECURE` | `true` |
| `SHARED_LIMITS` | `true` |
| `ALLOWED_HOSTS` | JSON array of exact hostnames, e.g. `["rumi-portfolio-demo.vercel.app"]`; no scheme/path/wildcard |
| `PROCESSOR_MODE` | `demo` initially |
| `PUBLIC_DEMO_LIVE` | `false` initially |
| `GEMINI_DAILY_LIMIT` | `10` (set `0` to stop all new Gemini calls) |
| `GEMINI_TOTAL_LIMIT` | `100` (persistent total for this database) |
| `SESSION_MINUTES` | `60` |
| `AI_TIMEOUT_SECONDS` | `20` |
| `AI_MAX_OUTPUT_TOKENS` | `1200` |

`FAQ_PATH` is unnecessary in portfolio mode: code always selects the packaged
fictional `app/demo_data/faq.json`, even if a private path is mistakenly configured.
Do not upload the ignored private FAQ. Leave `GEMINI_API_KEY` absent for the initial
demo deployment. Saved fixtures and simulations work without it.

Optional live generation requires **all** of `PROCESSOR_MODE=gemini`,
`PUBLIC_DEMO_LIVE=true`, a server-only sensitive `GEMINI_API_KEY`, and
`GEMINI_MODEL=gemini-3.5-flash-lite` (verify model availability and free quota in your
existing AI Studio project before enabling). Use an unbilled/free-quota project.
The application does not establish that a key is unbilled: the model name and app
budgets cannot guarantee zero provider cost. Do not enable billing or change plans
as a fallback. Provider quota/auth/model/timeout failures are shown explicitly.

Vercel sets `VERCEL` itself. When it is present, startup refuses local mode. Portfolio
mode refuses SQLite, insecure cookies, disabled shared limits, wildcard/empty host
lists, and a database URL without required TLS. Add an exact preview/deployment
hostname only when you intend to visit it; broad `*.vercel.app` is rejected.

## 3. Initialize the fresh database and create its administrator privately

From this project directory in a terminal, activate the existing virtual environment
or create an isolated one under ignored `artifacts/`. Install the verified lockfile
and project. On Windows PowerShell, for example:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.lock
.venv/Scripts/python.exe -m pip install --no-deps -e .
.venv/Scripts/python.exe -m app.cli migrate-db --database-url-prompt
.venv/Scripts/python.exe -m app.cli create-admin --database-url-prompt
```

Each command asks for the **new Rumi direct Neon URL without echo**. Check the
project/database selection in Neon before copying it. The prompt option ignores the
local `.env`; it does not write a new one. Do not put the URL in command arguments.
The administrator command then asks for username and a new password (12–256
characters), with hidden password confirmation. Use a unique cloud password;
do not reuse the local administrator's password. Store it in your password manager.
Argon2 hashes go only into the new database. The CLI refuses password echo fallback
and refuses to replace an existing administrator. There is no HTTP bootstrap route.

The PostgreSQL migration is revision **1**, independently numbered from SQLite.
It requires an empty database for first initialization, creates model tables/indexes
and `rumi_schema` inside one transaction, and seeds fixed shared-budget rows. A
transaction-scoped advisory lock serializes concurrent CLI migrations. Repeating
revision 1 preserves existing records and usage counts. Unknown revisions and
incomplete schemas are refused; cold starts only check, never initialize or migrate.
For future cloud revisions, take/verify a private `pg_dump` backup or a Neon restore
point before applying reviewed migrations; do not put backups in Git or Vercel.

Local SQLite stays the default. Its explicit migration is revision **3**, an additive
upgrade adding the demo and shared-budget tables. Stop the local server, then run
`python -m app.cli migrate-db` with no prompt option to back up and upgrade the local
database. It preserves the administrator, records, drafts, statuses, and sessions.
Preparation intentionally does not execute this command on your existing database.
Restart locally with `--host 127.0.0.1 --no-access-log`. Never change the local `.env`
to point at the portfolio DB merely to perform cloud initialization.

## 4. Import and deploy on Vercel (later, manually)

1. In the existing personal Hobby account, choose **Add New → Project → Import Git
   Repository** and select `SalmanAliAqdas/rumi-enquiry-assistant`. Create a **new Rumi
   project**, not a SchoolOS project. Confirm this remains personal/noncommercial use.
2. Set Root Directory to the repository root (`.`), Framework Preset **FastAPI**,
   production branch `main`. The committed `.python-version` selects Python **3.13**.
   Keep the framework's default install
   and build commands; leave Output Directory unset. No frontend build is required.
   `pyproject.toml` declares runtime dependencies and `app.main:app`; `vercel.json`
   declares FastAPI and a 60-second function limit. `requirements.lock` is the
   reproducible development/verification lock; Vercel reads `pyproject.toml`.
3. Set the environment variables above **before** the first deployment. Choose the
   function region nearest the new Neon database in the Rumi project settings.
   Ensure the planned production hostname exactly matches `ALLOWED_HOSTS`.
4. Review the source/bundle exclusions. `.vercelignore`, function `excludeFiles`,
   Git ignores, and package data keep `.env`, SQLite data, private knowledge,
   backups/exports, artifacts, and virtual environments out. Templates, static assets,
   and fictional demo JSON are included. Do not upload the whole local folder with
   another tool. Only public CSS/JS are mounted as static files.
5. Click Deploy only after the initialization/admin steps succeed and a separate
   hosting review is complete. Connecting Git enables future push deployments;
   take that into account before connecting the project. This preparation performs
   no Vercel import, resource creation, environment updates, or deployment.

## 5. Live verification after deployment

1. Visit the exact HTTPS production hostname: `/` redirects to `/explore`. Confirm
   fictional banners, three saved hand-authored examples, simulation, and a disabled
   live-generation notice. Check mobile layout, keyboard access, CSS/JS loading,
   and successful navigation without a browser console error.
2. Inspect the session cookie: `Secure`, `HttpOnly`, `SameSite=Strict`, path `/`.
   Confirm no private response is cached. Unapproved Host headers should return 400.
3. Anonymous `/admin` redirects to login; `/api/admin/enquiries`, its detail routes,
   and `/api/admin/status` return 401. Do not make real records to test this.
   Arbitrary `/api/enquiries` POSTs return 403 in portfolio mode. No public endpoint
   retrieves demo runs or real enquiries by ID/reference. Simulation/live forms
   reject missing or invalid CSRF tokens. Saved examples come exclusively from JSON.
4. Log in with the newly created cloud administrator. Confirm the private inbox is
   empty on a fresh database and the fictional FAQ projection is approved. The private
   **New test enquiry** form can then save fictional name/email/message records,
   process them in the configured mode, and open their review page. Existing request
   and Gemini budgets apply; `PUBLIC_DEMO_LIVE` controls the public demo only. These
   `REA-TEST-` records remain private. No schema or environment changes are needed
   for this feature. Visit Explore Demo and confirm
   it does not log the administrator out. Log out and confirm private API rejection.
5. Check Neon `rumi_schema` is version 1 and the administrator exists using the
   console without exporting it. Confirm there are no copied local enquiries.
6. In a separate preview/test database, verify request limits across two function
   instances and that database/guard failure denies requests. Shared limits are
   global: 120 dynamic requests/minute, 5 login POSTs/5 minutes, 20 submission/live
   POSTs/hour. They use database time and atomic row locks, ignore forwarded IPs,
   persist through cold starts, and return 429 or 503. A busy visitor can consume
   this intentionally small shared demo allowance; no IP-fairness guarantee is made.
7. If you explicitly enable live generation later, test **one fictional sample**.
   Confirm `Live-generated (saved fictional run)`, a saved `demorun` result, no
   private enquiry created, and no outgoing email. Failure must show an explicit
   error with no simulated substitute. Check the Gemini shared `used` and `total`
   counters increase. Never run a live model as part of normal tests or CI.
8. Global Gemini limits cover every app model path, reserve before calling, and
   count failures/timeouts too. One 90-second lease bounds active calls across
   instances; the call timeout is at most 60 seconds. Crashes retain the lease until
   expiry and consume usage. Fixed UTC-day windows may allow two allowances around
   midnight; the persistent total cap still applies. No automatic counter reset or
   refund occurs, including on administrator login or migration. Keep limits small;
   disabling `PUBLIC_DEMO_LIVE` stops public starts, setting the daily limit to zero
   stops all new model starts after the updated configuration is deployed.
9. Review runtime logs for sanitized errors without request bodies, secrets, URLs,
   or passwords. Check Vercel, Neon, and provider usage dashboards. Free-plan quotas,
   cold starts, and resource availability can still make the demo unavailable.

## Local verification without cloud resources

```powershell
.venv/Scripts/python.exe -m pytest
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/python.exe -m pip check
```

For PostgreSQL verification, start a disposable local PostgreSQL server and create
an empty administrative test DB named `rumi_test` with a role allowed to create DBs.
Set `TEST_POSTGRES_URL` in the test process only, pointing at **localhost** and that
database. Run the same pytest command. Tests create a randomly named separate DB
for each parametrized test and drop only those created DBs. The fixture refuses
remote hosts and any base database name other than `rumi_test`. Never point it at
Neon or an existing application database. Providers are mocked or blocked in tests.
CI includes a disposable PostgreSQL service; a skipped PostgreSQL test is not a pass.

See `PROJECT_STATUS.md` for checks actually run. This runbook is not evidence of a
Neon connection, Vercel build, deployment, or live-host verification.
