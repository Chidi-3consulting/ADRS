import bcrypt
from itsdangerous import URLSafeSerializer
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import RedirectResponse
from app.config import SECRET_KEY

serializer = URLSafeSerializer(SECRET_KEY, salt="adrs-session-salt")

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
        samesite="lax",
        secure=False  # Set True in production with HTTPS
    )

def clear_session(response: Response):
    response.delete_cookie("adrs_session")

# Middleware dependencies
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
