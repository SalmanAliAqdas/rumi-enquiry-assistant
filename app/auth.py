import hashlib
import secrets
from datetime import UTC, timedelta

from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from sqlmodel import Session, delete, select

from app.db import get_db
from app.models import Admin, WebSession, utcnow

password_hasher = PasswordHash.recommended()
# Prevent username enumeration via an obviously shorter password-verification path.
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))
COOKIE = "rumi_session"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_session(request: Request, db: Session = Depends(get_db)) -> WebSession:
    token = request.cookies.get(COOKIE, "")
    session = db.get(WebSession, hash_token(token)) if token else None
    if session is None or session.expires_at.replace(tzinfo=UTC) <= utcnow():
        raise HTTPException(401, "Please log in to continue.")
    return session


def require_admin(
    session: WebSession = Depends(current_session), db: Session = Depends(get_db)
) -> WebSession:
    if session.admin_id is None or db.get(Admin, session.admin_id) is None:
        raise HTTPException(401, "Please log in to continue.")
    return session


async def csrf_protect(request: Request, session: WebSession = Depends(current_session)):
    token = request.headers.get("X-CSRF-Token")
    if token is None and request.headers.get("content-type", "").startswith(
        "application/x-www-form-urlencoded"
    ):
        token = (await request.form()).get("csrf_token")
    if not isinstance(token, str) or not secrets.compare_digest(token, session.csrf_token):
        raise HTTPException(403, "Security token invalid. Reload the page and try again.")


def issue_session(request: Request, response, db: Session, admin_id: int | None = None):
    now = utcnow()
    db.exec(delete(WebSession).where(WebSession.expires_at <= now))
    old = request.cookies.get(COOKIE)
    if old:
        db.exec(delete(WebSession).where(WebSession.token_hash == hash_token(old)))
    token = secrets.token_urlsafe(32)
    session = WebSession(
        token_hash=hash_token(token),
        csrf_token=secrets.token_urlsafe(32),
        admin_id=admin_id,
        expires_at=now + timedelta(minutes=request.app.state.settings.session_minutes),
    )
    db.add(session)
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        max_age=request.app.state.settings.session_minutes * 60,
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return session


def verify_login(db: Session, username: str, password: str) -> Admin | None:
    admin = db.exec(select(Admin).where(Admin.username == username)).first()
    valid = password_hasher.verify(password, admin.password_hash if admin else DUMMY_HASH)
    return admin if valid else None
