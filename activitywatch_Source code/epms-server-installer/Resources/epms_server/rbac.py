"""
RBAC middleware for EPMS Enterprise Server.
Enforces role-based access: employee sees own data,
manager sees team, admin/super_admin sees all.
"""

import logging
import secrets
import os
import uuid
from enum import IntEnum
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, Header

logger = logging.getLogger("epms.server.rbac")


class Role(IntEnum):
    EMPLOYEE = 0
    MANAGER = 1
    ADMIN = 2
    SUPER_ADMIN = 3


ROLE_MAP = {
    "employee": Role.EMPLOYEE,
    "manager": Role.MANAGER,
    "admin": Role.ADMIN,
    "super_admin": Role.SUPER_ADMIN,
}


class AuthContext:
    """Holds authenticated user context including the raw token and JWT ID for logout."""
    def __init__(self, user_id: str, email: str, role: str, token: str = "", jti: str = "", org_id: str = ""):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.token = token
        self.jti = jti
        _o = org_id.strip() if org_id else ""
        self.org_id = uuid.UUID(_o) if _o.count("-") == 4 else ""


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token. Raises on invalid/expired."""
    try:
        import jwt as pyjwt
    except ImportError:
        raise HTTPException(status_code=500, detail="PyJWT not installed")
    from epms_server.config import JWT_SECRET, JWT_ALGORITHM

    try:
        payload = pyjwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"verify_exp": True},
        )
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or malformed token")


async def get_current_user(
    authorization: str = Header(None),
) -> AuthContext:
    """Verify JWT bearer token from authorization header.
    Returns AuthContext with user info, raw token, and jti for logout."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]
    payload = decode_token(token)

    # Verify it's an access token, not a refresh token
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    # Check if token is blacklisted (logged out)
    from epms_server import config
    if config.redis_client:
        is_blacklisted = await config.redis_client.get(f"{config.TOKEN_BLACKLIST_PREFIX}{payload.get('jti')}")
        if is_blacklisted:
            raise HTTPException(status_code=401, detail="Token has been revoked")

    return AuthContext(
        user_id=payload["sub"],
        email=payload.get("email", ""),
        role=payload.get("role", "user"),
        token=token,
        jti=payload.get("jti", ""),
        org_id=payload.get("org_id", ""),
    )


def require_role(min_role: str):
    """Dependency factory: returns a FastAPI dependency that checks the user's role.

    Usage:
        @app.get("/api/v1/sensitive-data")
        async def sensitive_endpoint(
            current_user: AuthContext = Depends(get_current_user),
            _rbac = Depends(require_role("manager")),
        ):
            ...
    """
    from fastapi import Depends, HTTPException

    min_role_enum = ROLE_MAP.get(min_role)
    if min_role_enum is None:
        raise ValueError(f"Unknown role: {min_role}")

    async def role_checker(current_user: AuthContext = Depends(get_current_user)) -> None:
        user_role_enum = ROLE_MAP.get(current_user.role, Role.EMPLOYEE)
        if user_role_enum < min_role_enum:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required role: {min_role}",
            )

    return role_checker


def filter_by_role(current_user, query_table_alias: str = "a") -> str:
    """Generate a SQL WHERE clause for role-based data filtering.

    - employee: WHERE a.agent_id = '<user_id>' (sees own data)
    - manager:  WHERE a.organization_id = '<org_id>' (sees all in org)
    - admin/super_admin: no filter (sees all)

    NOTE: Uses f-strings with JWT-derived values. org_id and user_id originate
    from JWT claims, not user input, so direct injection isn't feasible without
    JWT secret compromise. If this function is ever repurposed with user-supplied
    values, convert to parameterized queries ($1, $2).

    Caller must pass the AuthContext and the table alias for agents.
    Returns empty string for admin/super_admin (no filter).
    """
    role_enum = ROLE_MAP.get(current_user.role, Role.EMPLOYEE)

    if role_enum >= Role.ADMIN:
        return ""

    if role_enum == Role.MANAGER and current_user.org_id:
        return f"AND {query_table_alias}.organization_id = '{str(current_user.org_id)}'::uuid"

    # Employee — see own data only
    return f"AND {query_table_alias}.agent_id = '{current_user.user_id}'"


def can_access_agent(current_user, agent_org_id: str) -> bool:
    """Check if the current user can access data for a given agent."""
    role_enum = ROLE_MAP.get(current_user.role, Role.EMPLOYEE)

    if role_enum >= Role.ADMIN:
        return True

    if role_enum == Role.MANAGER and current_user.org_id:
        return agent_org_id == current_user.org_id

    return current_user.user_id == agent_org_id
