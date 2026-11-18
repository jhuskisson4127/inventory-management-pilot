import hashlib
import re
import secrets
from collections import OrderedDict, deque
from threading import BoundedSemaphore, Lock
from time import monotonic, time

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .db import get_db
from .models import LoginSession, User
from .settings import settings

router = APIRouter(prefix="/api/auth")
password_hasher = PasswordHasher()
dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))
session_seconds = 8 * 60 * 60
login_window = 60
login_attempts = OrderedDict()
login_lock = Lock()
password_checks = BoundedSemaphore(2)


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


def normalize_username(username: str) -> str:
    username = username.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.@+-]{0,63}", username):
        raise ValueError("Use 1–64 letters, digits, or ._@+- for the username.")
    return username


def require_csrf_header(request: Request):
    # A browser must preflight cross-origin requests with this custom header.
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("X-Inventory-Request") != "1":
            raise HTTPException(403, "Missing request verification header")


def throttle_login(request: Request):
    address = request.client.host if request.client else ""
    now = monotonic()
    with login_lock:
        while login_attempts:
            oldest = next(iter(login_attempts.values()))
            if now - oldest[-1] < login_window:
                break
            login_attempts.popitem(last=False)
        if address not in login_attempts and len(login_attempts) >= 4096:
            raise HTTPException(429, "Too many sign-in attempts")
        attempts = login_attempts.setdefault(address, deque())
        while attempts and now - attempts[0] >= login_window:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(429, "Too many sign-in attempts", headers={"Retry-After": "60"})
        attempts.append(now)
        login_attempts.move_to_end(address)


def cookie_name() -> str:
    return "__Host-inventory_session" if settings.session_cookie_secure else "inventory_session"


def session_digest(request: Request) -> str | None:
    token = request.cookies.get(cookie_name(), "")
    if re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return hashlib.sha256(token.encode()).hexdigest()
    return None


def session_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    digest = session_digest(request)
    session = db.get(LoginSession, digest) if digest else None
    if session is None or session.expires_at <= int(time()):
        return None
    return session.user


def require_user(user: User | None = Depends(session_user)) -> User:
    if user is None:
        raise HTTPException(401, "Sign in required")
    return user


@router.post("/login", dependencies=[Depends(require_csrf_header), Depends(throttle_login)])
def login(credentials: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        username = normalize_username(credentials.username)
    except ValueError:
        username = None
    user = db.get(User, username) if username else None
    if not password_checks.acquire(blocking=False):
        raise HTTPException(429, "Too many sign-in attempts", headers={"Retry-After": "1"})
    try:
        password_hasher.verify(user.password_hash if user else dummy_hash, credentials.password)
    except VerificationError:
        raise HTTPException(401, "Invalid username or password") from None
    finally:
        password_checks.release()
    if user is None:
        raise HTTPException(401, "Invalid username or password")

    username = user.username
    now = int(time())
    # Commit expiration cleanup before inserting to release MySQL range locks.
    db.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
    db.commit()
    previous_digest = session_digest(request)
    if previous_digest:
        previous_session = db.get(LoginSession, previous_digest)
        if previous_session is not None:
            db.delete(previous_session)
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(
        digest=hashlib.sha256(token.encode()).hexdigest(),
        username=username,
        expires_at=now + session_seconds,
    ))
    db.commit()
    response.set_cookie(cookie_name(), token, max_age=session_seconds, path="/",
                        secure=settings.session_cookie_secure, httponly=True, samesite="lax")
    return {"username": username}


@router.get("/session")
def current_session(user: User = Depends(require_user)):
    return {"username": user.username}


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf_header)])
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    digest = session_digest(request)
    if digest:
        db.execute(delete(LoginSession).where(LoginSession.digest == digest))
        db.commit()
    response.delete_cookie(cookie_name(), path="/", secure=settings.session_cookie_secure,
                           httponly=True, samesite="lax")
