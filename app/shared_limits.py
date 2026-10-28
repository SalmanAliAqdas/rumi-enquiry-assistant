"""Database-serialized budgets shared by all instances; errors deny admission."""

from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.models import SharedBudget


class SharedLimits:
    def __init__(self, engine):
        self.engine = engine

    def take(self, scope, limit, window, *, total_limit=None, lease=False):
        token = uuid4().hex if lease else None
        try:
            with Session(self.engine) as db:
                if self.engine.dialect.name == "sqlite":
                    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
                row = db.exec(
                    select(SharedBudget).where(SharedBudget.scope == scope).with_for_update()
                ).one()
                # Database time avoids disagreement between serverless instance clocks.
                clock_sql = (
                    "SELECT EXTRACT(EPOCH FROM clock_timestamp())"
                    if self.engine.dialect.name == "postgresql"
                    else "SELECT (julianday('now') - 2440587.5) * 86400"
                )
                now = float(db.execute(text(clock_sql)).scalar_one())
                start = (now // window) * window
                used = row.used if row.window_start == start else 0
                if used >= limit or (total_limit is not None and row.total >= total_limit):
                    return "shared_limit", None
                if lease and row.lease_until > now:
                    return "shared_busy", None
                row.window_start, row.used = start, used + 1
                # Only the Gemini lifetime counter needs to grow indefinitely.
                row.total = row.total + 1 if total_limit is not None else 0
                if lease:
                    row.lease_token, row.lease_until = token, now + 90
                db.add(row)
                db.commit()
                return None, token
        except (SQLAlchemyError, ValueError):
            return "shared_unavailable", None

    def release(self, token):
        from sqlalchemy import update

        try:
            with self.engine.begin() as connection:
                connection.execute(
                    update(SharedBudget)
                    .where(SharedBudget.scope == "gemini", SharedBudget.lease_token == token)
                    .values(lease_until=0, lease_token=None)
                )
        except SQLAlchemyError:
            pass  # Lease expires; never open the guard on a failed release.


async def run_processor(app, message):
    """All Gemini paths share the same local and durable global admission gates."""
    import asyncio

    from app.services import ProcessingFailure

    admitted = False
    token = None
    try:
        if app.state.processing_mode == "gemini":
            code, _ = app.state.processing_budget.enter()
            if code:
                raise ProcessingFailure(code)
            admitted = True
            settings = app.state.settings
            if settings.shared_limits:
                code, token = await asyncio.to_thread(
                    app.state.shared_limits.take,
                    "gemini",
                    settings.gemini_daily_limit,
                    86400,
                    total_limit=settings.gemini_total_limit,
                    lease=True,
                )
                if code:
                    raise ProcessingFailure(code)
        return await asyncio.wait_for(
            app.state.processor.process(message), timeout=app.state.processing_timeout
        )
    finally:
        if token:
            await asyncio.to_thread(app.state.shared_limits.release, token)
        if admitted:
            app.state.processing_budget.leave()
