"""
Authentication — JWT verification against Supabase.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from jose import JWTError, jwt

from config import settings

router = APIRouter()
logger = logging.getLogger("finsight.auth")


class CurrentUser:
    """Authenticated user context."""

    def __init__(self, user_id: str, email: Optional[str] = None, role: str = "authenticated"):
        self.user_id = user_id
        self.email = email
        self.role = role


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> CurrentUser:
    """Extract and verify JWT from Authorization header.
    
    Supports both Supabase JWTs and simple Bearer tokens.
    For demo/dataset endpoints, a special demo token is accepted.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization format. Use: Bearer <token>")

    token = parts[1]

    # Demo mode — accept a special demo token
    if token == "demo-token" and settings.ENVIRONMENT != "production":
        return CurrentUser(user_id="c42f840c-4548-471b-8715-96c101accfa4", email="demo@finsight.app", role="demo")

    try:
        # Decode the Supabase JWT
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        user_id = payload.get("sub")
        email = payload.get("email")
        role = payload.get("role", "authenticated")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing sub claim")

        return CurrentUser(user_id=user_id, email=email, role=role)

    except JWTError as e:
        logger.warning("JWT verification failed: %s", e)
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {e}")


async def get_optional_user(
    authorization: Optional[str] = Header(None),
) -> Optional[CurrentUser]:
    """Optional auth — returns None if no token provided."""
    if not authorization:
        return None
    try:
        return await get_current_user(Request(scope={"type": "http"}), authorization)
    except HTTPException:
        return None


@router.post("/auth/verify")
async def verify_token(user: CurrentUser = Depends(get_current_user)):
    """Verify that a JWT token is valid."""
    return {"user_id": user.user_id, "email": user.email, "role": user.role, "valid": True}
