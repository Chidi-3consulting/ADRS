"""
ADRS Authentication

Provides: password hashing/verification, session management (signed cookies),
role-based access, login throttling, and password policy enforcement.
"""
import time
import bcrypt
from datetime import datetime, timedelta
from itsdangerous import URLSafeSerializer
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import (
    SECRET_KEY, COOKIE_SECURE, COOKIE_SAMESITE,
    LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_MINUTES, PASSWORD_MIN_LENGTH,
)

serializer = URLSafeSerializer(SECRET_KEY, salt="adrs-session-salt")


# ── Password Hashing (bcrypt) ──

def hash_password(password: str) -> str:
    passwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(passwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        passwd_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(passwd_bytes, hashed_bytes)
    except Exception:
        return False


# ── Password Policy  ──

def password_policy_error(password: str) -> str | None:
    """
    Returns an error message if password fails policy, else None.
    Policy: min 10 chars, must include both letters and numbers.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not has_letter or not has_digit:
        return "Password must include both letters and numbers."
    return None


# ── Session Management (signed cookie) ──

def get_session(request: Request) -> dict:
    cookie = request.cookies.get("adrs_session")
    if not cookie:
        return {}
    try:
        return serializer.loads(cookie)
    except Exception:
        return {}


def set_session(response: Response, data: dict):
    val = serializer.dumps(data)
    response.set_cookie(
        key="adrs_session",
        value=val,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
    )


def clear_session(response: Response):
    response.delete_cookie("adrs_session")


def build_session_data(user, org, extra: dict = None) -> dict:
    """
    Build the canonical session dict from a User + Organization ORM row.
    Includes timestamps for timeout enforcement.
    """
    now = time.time()
    data = {
        "user_id": user.id,
        "user_name": user.name,
        "email": user.email,
        "role": user.role,
        "org_id": org.id,
        "org_name": org.name,
        "org_domain": org.primary_domain,
        "org_status": org.status,
        "country": org.country or "OTHER",
        "is_platform_admin": user.is_platform_admin,
        "must_change_password": bool(user.must_change_password),
        "twofa_enabled": bool(user.twofa_enabled),
        "email_verified": user.email_verified_at is not None,
        "subscription_status": org.subscription_status or "trial",
        "trial_ends_at": org.trial_ends_at.isoformat() if org.trial_ends_at else None,
        "login_time": now,
        "last_activity": now,
    }
    if extra:
        data.update(extra)
    return data


# ── Middleware Dependencies ──

def current_user(request: Request) -> dict:
    session = get_session(request)
    if not session or "user_id" not in session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return session


def require_role(roles: list):
    def dependency(request: Request):
        user = get_session(request)
        if not user or "user_id" not in user:
            # For web pages, redirect to login
            raise HTTPException(status_code=303, detail="Redirect to login")
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Permission denied")
        return user
    return dependency


# ── Login Brute-Force Throttling ──

def record_login_attempt(db: Session, email: str, ip: str, success: bool) -> None:
    """
    Record a login attempt (success or failure). Never throws — throttling
    must not break the login flow.
    """
    try:
        from app.models import LoginAttempt
        attempt = LoginAttempt(
            email=email if email else None,
            ip_address=ip,
            success=success,
        )
        db.add(attempt)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def login_throttle_seconds(db: Session, email: str, ip: str) -> int:
    """
    Seconds the caller must wait before retrying, or 0 if not throttled.
    Locks after LOGIN_MAX_ATTEMPTS failed attempts for the same email OR IP
    within a LOGIN_WINDOW_MINUTES rolling window.
    """
    try:
        from app.models import LoginAttempt
        from sqlalchemy import func

        window_start = datetime.utcnow() - timedelta(minutes=LOGIN_WINDOW_MINUTES)
        count = db.query(func.count(LoginAttempt.id)).filter(
            LoginAttempt.success == False,
            LoginAttempt.created_at >= window_start,
            (LoginAttempt.email == email) | (LoginAttempt.ip_address == ip),
        ).scalar() or 0

        if count < LOGIN_MAX_ATTEMPTS:
            return 0

        # Find earliest attempt in window to compute remaining lockout
        earliest = db.query(func.min(LoginAttempt.created_at)).filter(
            LoginAttempt.success == False,
            LoginAttempt.created_at >= window_start,
            (LoginAttempt.email == email) | (LoginAttempt.ip_address == ip),
        ).scalar()

        if earliest:
            unlock_at = earliest + timedelta(minutes=LOGIN_WINDOW_MINUTES)
            remaining = (unlock_at - datetime.utcnow()).total_seconds()
            return max(1, int(remaining))
        return 0
    except Exception:
        return 0  # Fail open — never break login


# ── Email Verification  ──

def issue_email_verification_token(db: Session, user_id: int) -> str:
    """
    Generate a random verification token, store its SHA-256 hash
    as a PasswordReset row with type context, and return the raw token.
    
    """
    import secrets
    import hashlib
    from app.models import PasswordReset, User

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return ""

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    reset = PasswordReset(
        email=user.email,
        token_hash=f"ev_{token_hash}",  # Prefix to distinguish from password resets
        expires_at=datetime.utcnow() + timedelta(hours=24),
        used=False,
    )
    db.add(reset)
    db.commit()
    return raw_token


def verify_email_token(db: Session, token: str) -> bool:
    """
    Validate an email verification token, mark the user's email as verified
    (clear must_change_password used as email_verified proxy), and consume the token.
    Returns True if successful.
    """
    import hashlib
    from app.models import PasswordReset, User

    token_hash = f"ev_{hashlib.sha256(token.encode('utf-8')).hexdigest()}"
    reset = db.query(PasswordReset).filter(
        PasswordReset.token_hash == token_hash,
        PasswordReset.used == False,
        PasswordReset.expires_at >= datetime.utcnow(),
    ).first()

    if not reset:
        return False

    user = db.query(User).filter(User.email == reset.email).first()
    if not user:
        return False

    user.email_verified_at = datetime.utcnow()
    reset.used = True
    db.commit()
    return True


def setup_is_complete(db: Session) -> bool:
    """Check if initial setup has been completed (system_settings key)."""
    from app.models import SystemSetting
    row = db.query(SystemSetting).filter(
        SystemSetting.setting_key == "setup_complete"
    ).first()
    return row is not None and row.setting_value == "1"
