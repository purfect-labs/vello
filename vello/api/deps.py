from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Cookie, HTTPException
import jwt

from vello.config import SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES
from vello.database import get_user_by_id


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, SECRET_KEY, algorithm="HS256")


def get_current_user(vello_token: Optional[str] = Cookie(default=None)):
    if not vello_token:
        raise HTTPException(status_code=401, detail="not_authenticated")
    try:
        payload = jwt.decode(vello_token, SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub", "")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid_token")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="user_not_found")
    return user
