"""
SafeData Authentication

Provides: password hashing/verification, session management (signed cookies),
role-based access, login throttling, and password policy enforcement.
"""
import time
import secrets
import os
import bcrypt
from datetime import datetime, timedelta, timezone
from itsdangerous import URLSafeSerializer
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import (
    SECRET_KEY, COOKIE_SECURE, COOKIE_SAMESITE,
    LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_MINUTES, PASSWORD_MIN_LENGTH,
    PASSWORD_HISTORY_COUNT, IS_TEST,
)
import base64
import hashlib
from cryptography.fernet import Fernet

serializer = URLSafeSerializer(SECRET_KEY, salt="SafeData-session-salt")

# ── TOTP Secret Encryption at Rest (AES-128-CBC + HMAC-SHA256) ──

def _get_totp_fernet_key() -> bytes:
    digest = hashlib.sha256(f"SafeData_TOTP_KEY_{SECRET_KEY}".encode()).digest()
    return base64.urlsafe_b64encode(digest)

def encrypt_totp_secret(secret_b32: str) -> str:
    """Encrypt TOTP secret at rest using Fernet."""
    if not secret_b32:
        return ""
    f = Fernet(_get_totp_fernet_key())
    return f.encrypt(secret_b32.strip().encode()).decode()

def decrypt_totp_secret(stored_secret: str) -> str:
    """Decrypt TOTP secret. Backward-compatible with plaintext base32 secrets."""
    if not stored_secret:
        return ""
    if not stored_secret.startswith("gAAAAA"):
        return stored_secret
    try:
        f = Fernet(_get_totp_fernet_key())
        return f.decrypt(stored_secret.encode()).decode()
    except Exception:
        return stored_secret


# ── Password Hashing (bcrypt) ──

def hash_password(password: str) -> str:
    passwd_bytes = password.encode('utf-8')
    from app.config import BCRYPT_ROUNDS
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(passwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        passwd_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(passwd_bytes, hashed_bytes)
    except Exception:
        return False


# A fixed, never-matching hash so callers can run `verify_password` against it
# when no user record was found — bcrypt.checkpw still does its full work, so
# the response takes the same time as a wrong-password attempt on a real
# account. Without this, "no such user" returns faster than "wrong password",
# which lets an attacker enumerate valid emails from response latency alone.
DUMMY_PASSWORD_HASH = bcrypt.hashpw(os.urandom(32).hex().encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


# ── Password Policy (Gap 2: strengthened) ──

# Top 100 most common passwords (lowercase) for dictionary check
_COMMON_PASSWORDS = frozenset([
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "1234567",
    "letmein", "trustno1", "dragon", "baseball", "iloveyou", "master", "sunshine",
    "ashley", "bailey", "shadow", "123456789", "1234567890", "password1",
    "password123", "admin", "administrator", "welcome", "welcome1", "p@ssw0rd",
    "passw0rd", "football", "charlie", "donald", "michael", "jennifer", "jordan",
    "superman", "harley", "robert", "thomas", "hockey", "ranger", "daniel",
    "starwars", "klaster", "george", "computer", "michelle", "jessica", "pepper",
    "1111", "zxcvbn", "555555", "11111111", "131313", "freedom", "7777777",
    "pass", "maggie", "159753", "aaaaaa", "ginger", "princess", "joshua",
    "cheese", "amanda", "summer", "love", "ashley1", "nicole", "chelsea",
    "matthew", "access", "yankees", "987654321", "dallas", "austin", "thunder",
    "taylor", "matrix", "william", "corvette", "hello", "martin", "heather",
    "secret", "merlin", "diamond", "1234qwer", "gfhjkm", "hammer", "silver",
    "222222", "88888888", "anthony", "justin", "test", "kitchen", "cookie",
    "robert1", "snoopy", "changeme", "changeme1", "qwerty123", "letmein1",
])


def password_policy_error(password: str, user_email: str = None, user_name: str = None) -> str | None:
    """
    Returns an error message if password fails policy, else None.
    Policy (Gap 2 — strengthened for production):
      - Min 10 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one digit
      - At least one special character
      - Not in common password list
      - Does not contain user's email or name
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
    if not any(c.isupper() for c in password):
        return "Password must include at least one uppercase letter."
    if not any(c.islower() for c in password):
        return "Password must include at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must include at least one number."
    if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for c in password):
        return "Password must include at least one special character (!@#$%^&* etc.)."
    if password.lower() in _COMMON_PASSWORDS:
        return "This password is too common. Please choose a more unique password."
    # Check if password contains the user's email or name
    if user_email:
        email_local = user_email.split("@")[0].lower()
        if len(email_local) >= 4 and email_local in password.lower():
            return "Password must not contain your email address."
    if user_name:
        name_lower = user_name.strip().lower()
        if len(name_lower) >= 4 and name_lower in password.lower():
            return "Password must not contain your name."
    return None


# ── Password History (Gap 3: prevent reuse) ──

def check_password_history(db: Session, user_id: int, new_password: str) -> bool:
    """
    Returns True if the new password matches any of the user's last
    PASSWORD_HISTORY_COUNT passwords. Returns False if safe to use.
    """
    from app.models import PasswordHistory
    recent = db.query(PasswordHistory).filter(
        PasswordHistory.user_id == user_id,
    ).order_by(PasswordHistory.created_at.desc()).limit(PASSWORD_HISTORY_COUNT).all()

    for entry in recent:
        if verify_password(new_password, entry.password_hash):
            return True  # Match found — password was recently used
    return False


def record_password_history(db: Session, user_id: int, password_hash: str) -> None:
    """
    Record a password hash in the user's history. Prunes entries beyond
    PASSWORD_HISTORY_COUNT to keep the table lean.
    """
    from app.models import PasswordHistory
    entry = PasswordHistory(
        user_id=user_id,
        password_hash=password_hash,
    )
    db.add(entry)
    db.flush()

    # Prune old entries beyond the configured history count
    all_entries = db.query(PasswordHistory).filter(
        PasswordHistory.user_id == user_id,
    ).order_by(PasswordHistory.created_at.desc()).all()

    if len(all_entries) > PASSWORD_HISTORY_COUNT:
        for old in all_entries[PASSWORD_HISTORY_COUNT:]:
            db.delete(old)
    db.commit()


# ── Session Management (signed cookie) ──

def get_session(request: Request) -> dict:
    # The session middleware re-reads role/status from the database; handlers must see that
    # fresh copy on this very request, not the possibly stale cookie.
    fresh = getattr(getattr(request, "state", None), "session_fresh", None)
    if fresh is not None:
        return fresh
    cookie = request.cookies.get("SafeData_session")
    if not cookie:
        return {}
    try:
        return serializer.loads(cookie)
    except Exception:
        return {}


def set_session(response: Response, data: dict):
    val = serializer.dumps(data)
    response.set_cookie(
        key="SafeData_session",
        value=val,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
    )


def clear_session(response: Response):
    response.delete_cookie("SafeData_session")


def password_fingerprint(password_hash: str) -> str:
    """Short, non-reversible tag of the current password hash. Kept in the session cookie so
    a password change or reset ends every other signed-in session."""
    return hashlib.sha256((password_hash or "").encode("utf-8")).hexdigest()[:16]


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
        "csrf_token": secrets.token_hex(32),
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
        "pw_fp": password_fingerprint(user.password_hash),
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

        window_start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=LOGIN_WINDOW_MINUTES)
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
            remaining = (unlock_at - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds()
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
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24),
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
        PasswordReset.expires_at >= datetime.now(timezone.utc).replace(tzinfo=None),
    ).first()

    if not reset:
        return False

    user = db.query(User).filter(User.email == reset.email).first()
    if not user:
        return False

    user.email_verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
    reset.used = True
    db.commit()
    return True


def setup_is_complete(db: Session) -> bool:
    """Check if initial setup has been completed (system_settings key)."""
    from app.models import SystemSetting, User
    row = db.query(SystemSetting).filter(
        SystemSetting.setting_key == "setup_complete"
    ).first()
    if row is not None and row.setting_value == "1":
        return True
    # Installs created with `create-admin` or the sign-up form never wrote the flag. Any
    # existing user means the system is already set up; otherwise the public /setup page
    # would let a stranger create an administrator on a live site.
    return db.query(User.id).first() is not None


# ── Step-Up Authentication (Safe Delete & High-Risk Actions) ──

def verify_stepup_authentication(db: Session, user_id: int, auth_credential: str, ip: str = "") -> tuple[bool, str]:
    """
    Verify step-up credentials (password or 2FA TOTP code) for sensitive operations
    (e.g., permanent disposal, bulk safe delete, legal hold changes).
    Returns (True, "OK") or (False, "Error message").
    """
    from app.models import User
    from app.helpers import totp_verify, consume_recovery_code

    if not auth_credential or not str(auth_credential).strip():
        return False, "Authentication credential (password or 2FA code) is required for safe delete."

    cred = str(auth_credential).strip()
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False, "User not found."

    # Guessing the password here is as good as guessing it at sign-in, so it shares that throttle.
    if login_throttle_seconds(db, user.email, ip or "stepup") > 0:
        return False, "Too many failed attempts. Try again later."
    ok, msg = _check_stepup(db, user, cred)
    if not ok:
        record_login_attempt(db, user.email, ip or "stepup", success=False)
    return ok, msg


def _check_stepup(db: Session, user, cred: str) -> tuple[bool, str]:
    from app.helpers import totp_verify, consume_recovery_code
    # 1. If user has 2FA enabled, check TOTP code or recovery code first
    if user.twofa_enabled and user.twofa_secret:
        if totp_verify(decrypt_totp_secret(user.twofa_secret), cred):
            return True, "OK"
        if user.twofa_recovery:
            try:
                import json as _json
                recovery_list = _json.loads(user.twofa_recovery) if isinstance(user.twofa_recovery, str) else (user.twofa_recovery or [])
                remaining = consume_recovery_code(recovery_list, cred)
                if remaining is not None:
                    user.twofa_recovery = _json.dumps(remaining)
                    db.commit()
                    return True, "OK"
            except Exception:
                pass

    # 2. Verify account password
    if user.password_hash and verify_password(cred, user.password_hash):
        return True, "OK"

    if user.twofa_enabled:
        return False, "Invalid account password or 2FA authenticator code."
    return False, "Invalid account password confirmation."
