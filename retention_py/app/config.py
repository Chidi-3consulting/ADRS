import os

# Base Directory of retention_py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Env config
APP_ENV = os.getenv("APP_ENV", "local")  # 'production' | 'local' | 'test'
IS_PRODUCTION = APP_ENV == "production"
APP_NAME = os.getenv("APP_NAME", "ADRS — 3Consulting Python")
APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8200")
SECRET_KEY = os.getenv("SECRET_KEY", "adrs_python_super_secret_session_key_3c_2026")

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

# ── CORS / Trusted Hosts ──
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*")  # comma-separated in production
TRUSTED_PROXIES = os.getenv("TRUSTED_PROXIES", "")  # comma-separated proxy IPs

# ── Cookie security ──
COOKIE_SECURE = IS_PRODUCTION  # True in production (HTTPS), False locally
COOKIE_SAMESITE = "lax"

# ── Backup ──
BACKUP_PATH = os.path.join(BASE_DIR, "storage", "backups")
os.makedirs(BACKUP_PATH, exist_ok=True)
