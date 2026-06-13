"""services/shared/auth.py — JWT token infrastructure for job ownership.

GA-A1: Provides create_token / verify_token plus FastAPI dependencies.
Secret from env CADHLLM_JWT_SECRET (dev fallback provided).
"""
from __future__ import annotations

import logging
import os
import warnings
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Header, HTTPException, WebSocket

_log = logging.getLogger(__name__)
_SECRET = os.environ.get("CADHLLM_JWT_SECRET", "")
if not _SECRET:
    # A hardcoded HS256 secret lets anyone forge job-ownership tokens, so the
    # dev fallback must be explicitly opted into. Without the opt-in flag, fail
    # loudly instead of silently signing/verifying with a publicly-known key.
    if os.environ.get("CADHLLM_ALLOW_DEV_SECRET", "").lower() in ("1", "true", "yes"):
        _SECRET = "cadhllm-dev-secret-change-in-prod"
        warnings.warn(
            "CADHLLM_JWT_SECRET not set — using insecure dev default because "
            "CADHLLM_ALLOW_DEV_SECRET is enabled. Never do this in production.",
            stacklevel=1,
        )
        _log.warning("CADHLLM_JWT_SECRET not set, using insecure dev fallback")
    else:
        raise RuntimeError(
            "CADHLLM_JWT_SECRET is not set. Refusing to start with a hardcoded "
            "JWT secret, which would allow forgery of job-ownership tokens. "
            "Set CADHLLM_JWT_SECRET, or set CADHLLM_ALLOW_DEV_SECRET=1 for "
            "local development only."
        )
_ALGORITHM = "HS256"
_DEFAULT_EXPIRE = timedelta(hours=2)


def create_token(job_id: str, expires_delta: timedelta = _DEFAULT_EXPIRE) -> str:
    payload = {
        "job_id": job_id,
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def verify_token(token: str) -> str:
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    job_id: str = payload.get("job_id", "")
    if not job_id:
        raise HTTPException(401, "Token missing job_id claim")
    return job_id


async def get_token_job_id(authorization: str = Header(...)) -> str:
    """FastAPI dependency: extract Bearer token, return verified job_id."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization must be 'Bearer <token>'")
    return verify_token(authorization[7:])


def require_job_owner(token_job_id: str, path_job_id: str) -> None:
    """Raise 403 if the token's job_id does not match the path parameter."""
    if token_job_id != path_job_id:
        raise HTTPException(403, "Token does not own this job")


async def verify_ws_ticket(ws: WebSocket, job_id: str, ticket: Optional[str]) -> bool:
    """Verify WebSocket ticket query param. Closes with 4001 on failure."""
    if not ticket:
        await ws.close(code=4001, reason="missing ticket")
        return False
    try:
        token_job_id = verify_token(ticket)
    except HTTPException:
        await ws.close(code=4001, reason="invalid ticket")
        return False
    if token_job_id != job_id:
        await ws.close(code=4001, reason="ticket job_id mismatch")
        return False
    return True
