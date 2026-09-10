import os
import sys
import secrets as _secrets
import warnings

# Base Directory of retention_py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Env config
APP_ENV = os.getenv("APP_ENV", "local")  # 'production' | 'local' | 'test'
IS_PRODUCTION = APP_ENV == "production"
IS_TEST = APP_ENV == "test"
APP_NAME = os.getenv("APP_NAME", "SafeData — 3Consulting Python")
APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8200")

# ── Security: Secret Key (Gap 1) ──
# The default is ONLY for local development. In production, a cryptographically
# random SECRET_KEY MUST be provided via environment variable.
_DEFAULT_SECRET = "SafeData_python_super_secret_session_key_3c_2026"
_env_secret = os.getenv("SECRET_KEY", "")

if _env_secret:
    SECRET_KEY = _env_secret
elif IS_PRODUCTION:
    print(
        "\n"
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║  FATAL: SECRET_KEY environment variable is not set.        ║\n"
        "║                                                            ║\n"
        "║  In production mode, you MUST provide a cryptographically  ║\n"
        "║  random SECRET_KEY. Generate one with:                     ║\n"
        "║                                                            ║\n"
        "║    python -c \"import secrets; print(secrets.token_hex(64))\"  ║\n"
        "║                                                            ║\n"
        "║  Then set it:  export SECRET_KEY='<your-key>'              ║\n"
        "╚══════════════════════════════════════════════════════════════╝\n",
        file=sys.stderr,
    )
    sys.exit(1)
else:
    SECRET_KEY = _DEFAULT_SECRET
    if not IS_TEST:
        warnings.warn(
            "SafeData: Using default SECRET_KEY — acceptable for local dev only. "
            "Set SECRET_KEY env var before deploying.",
            stacklevel=2,
        )

# Database URI (SQLite locally, MySQL in production)
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    f"sqlite:///{os.path.join(BASE_DIR, 'retention.db')}"
)

# Upload/Log paths
UPLOAD_PATH = os.path.join(BASE_DIR, "storage", "attachments")
LOG_PATH = os.path.join(BASE_DIR, "storage", "logs")

# Ensure paths exist
os.makedirs(UPLOAD_PATH, exist_ok=True)
os.makedirs(LOG_PATH, exist_ok=True)

# ── Security: Session Timeouts ──
SESSION_IDLE_TIMEOUT = 1800       # auto-logout after 30 min of inactivity
SESSION_ABSOLUTE_TIMEOUT = 28800  # hard cap of 8 hr per session

# ── Security: CSRF ──
CSRF_TOKEN_LENGTH = 32  # bytes → 64 hex chars

# ── Security: Login Throttle ──
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_MINUTES = 15

# ── Security: Password Policy ──
PASSWORD_MIN_LENGTH = 10
PASSWORD_HISTORY_COUNT = 5  # Number of previous passwords to check against

# ── Security: Request Size Limit (Gap 8) ──
MAX_REQUEST_BODY_SIZE = int(os.getenv("MAX_REQUEST_BODY_SIZE", str(25 * 1024 * 1024)))  # 25 MB

# ── CORS / Trusted Hosts ──
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*")  # comma-separated in production
TRUSTED_PROXIES = os.getenv("TRUSTED_PROXIES", "")  # comma-separated proxy IPs

# ── Cookie security ──
COOKIE_SECURE = IS_PRODUCTION  # True in production (HTTPS), False locally
COOKIE_SAMESITE = "lax"

# ── Backup ──
BACKUP_PATH = os.path.join(BASE_DIR, "storage", "backups")
os.makedirs(BACKUP_PATH, exist_ok=True)

# ── Platform Email (SMTP) ──
# Owned by 3Consulting as the platform operator.
# Set these as environment variables on Render — never stored in the app DB.
# Clients never see or configure these; emails are sent on their behalf automatically.
SMTP_HOST     = os.getenv("SMTP_HOST", "")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASS     = os.getenv("SMTP_PASS", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@3consulting.com")
SMTP_FROM_NAME  = os.getenv("SMTP_FROM_NAME", "SafeData by 3Consulting")
SMTP_SECURE   = os.getenv("SMTP_SECURE", "tls")  # 'tls' | 'ssl' | 'none'
# Reply-To address — clients can reply to support without exposing noreply@
# Set to your support/team email, e.g. support@3consulting.com
SMTP_REPLY_TO = os.getenv("SMTP_REPLY_TO", "")
