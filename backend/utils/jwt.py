import os
import datetime
from typing import Optional
import jwt
from dotenv import load_dotenv

load_dotenv()

# Load secret from environment (fallback to a development default)
JWT_SECRET = os.getenv("KINGIN_JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"

def create_token(user_id: str, expires_in: int = 3600) -> str:
    """Create a JWT token for the given user_id.
    expires_in: seconds until expiration (default 1 hour).
    """
    now = datetime.datetime.utcnow()
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    # PyJWT 2.x returns str, ensure string
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token.
    Returns the payload dict if valid, otherwise None.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
