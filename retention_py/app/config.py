import os

# Base Directory of retention_py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Env config
APP_ENV = os.getenv("APP_ENV", "local")  # 'production' | 'local' | 'test'
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
