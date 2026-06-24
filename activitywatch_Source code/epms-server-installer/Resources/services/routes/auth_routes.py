import os
import json
import base64
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Depends, Query

from routes.models import (
    HealthResponse, LoginRequest, ADLoginRequest, TokenResponse,
)
from routes.helpers import (
    _parse_ts, hash_password, verify_password,
    create_access_token, create_refresh_token,
    get_db, _aggregation_worker,
)
import routes.state as app_state

from epms_server.ad_login import authenticate_ad
from epms_server.config import (
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    TOKEN_BLACKLIST_PREFIX,
)
from epms_server.rbac import AuthContext, get_current_user, decode_token

router = APIRouter()


# ===== Health & Info =====

@router.get("/health", response_model=HealthResponse)
@router.get("/health/live")
@router.get("/health/ready")
async def health_check():
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        uptime_seconds=(datetime.now(timezone.utc) - app_state.start_time).total_seconds(),
        database="connected" if app_state.db_pool else "disconnected",
        redis="connected" if app_state.redis_client else "disabled",
    )


@router.get("/api/v1/health")
async def api_health():
    return {"status": "healthy", "service": "epms-api", "version": "1.0.0"}


@router.get("/api/v1/info")
async def server_info(current_user: AuthContext = Depends(get_current_user)):
    return {
        "name": "EPMS Enterprise Server",
        "version": "1.0.0",
        "uptime_seconds": (datetime.now(timezone.utc) - app_state.start_time).total_seconds(),
    }


# ===== Auth =====

@router.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
    email = credentials.email.strip().lower()
    if app_state.redis_client:
        attempt_key = f"login:attempts:{email}"
        attempts = await app_state.redis_client.get(attempt_key)
        if attempts and int(attempts) >= 5:
            ttl = await app_state.redis_client.ttl(attempt_key)
            raise HTTPException(
                status_code=429,
                detail=f"Too many login attempts. Try again in {ttl} seconds.",
            )
        await app_state.redis_client.incr(attempt_key)
        await app_state.redis_client.expire(attempt_key, 60)

    DEV_MODE = os.environ.get("EPMS_DEV_MODE", "").lower() in ("1", "true", "yes")
    DEV_CRED_B64 = os.environ.get("EPMS_DEV_CREDENTIALS", "")
    if DEV_MODE and DEV_CRED_B64:
        try:
            dev_creds = json.loads(base64.b64decode(DEV_CRED_B64).decode())
            if email == dev_creds.get("email", "") and credentials.password == dev_creds.get("password", ""):
                dev_user_id = dev_creds.get("user_id", "00000000-0000-0000-0000-000000000001")
                dev_role = dev_creds.get("role", "super_admin")
                dev_org_id = dev_creds.get("org_id", "00000000-0000-0000-0000-000000000000")
                access_token, access_exp = create_access_token(dev_user_id, email, dev_role, dev_org_id)
                refresh_token, refresh_exp = create_refresh_token(dev_user_id)
                return TokenResponse(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                    user={
                        "id": dev_user_id,
                        "email": email,
                        "display_name": dev_creds.get("display_name", "Administrator"),
                        "role": dev_role,
                        "organization_id": dev_org_id,
                        "mfa_enabled": False,
                    },
                )
        except Exception:
            pass

    if not app_state.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with app_state.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT u.id, u.email, u.password_hash, u.display_name, u.role,
               u.is_active, u.organization_id, u.mfa_enabled
               FROM users u WHERE u.email = $1 AND u.is_active = true""",
            email,
        )
        if not row:
            hash_password("dummy" + secrets.token_hex(8))
            raise HTTPException(status_code=401, detail="Invalid email or password")

        stored_hash = row["password_hash"]
        if not stored_hash or not verify_password(credentials.password, stored_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if app_state.redis_client:
            await app_state.redis_client.delete(f"login:attempts:{email}")

        user_id = str(row["id"])
        org_id = str(row["organization_id"]) if row.get("organization_id") else ""
        access_token, access_exp = create_access_token(user_id, row["email"], row["role"], org_id)
        refresh_token, refresh_exp = create_refresh_token(user_id)

        await conn.execute(
            "UPDATE users SET last_login = NOW() WHERE id = $1::uuid", user_id,
        )
        await conn.execute(
            """INSERT INTO user_sessions (user_id, refresh_token, expires_at)
               VALUES ($1, $2, to_timestamp($3))""",
            user_id, refresh_token, refresh_exp,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "id": user_id,
                "email": row["email"],
                "display_name": row["display_name"],
                "role": row["role"],
                "organization_id": str(row["organization_id"]),
                "mfa_enabled": row["mfa_enabled"],
            },
        )


@router.post("/api/v1/auth/ad-login", response_model=TokenResponse)
async def ad_login(credentials: ADLoginRequest):
    email = credentials.email.strip().lower()
    if app_state.redis_client:
        attempt_key = f"login:attempts:{email}"
        attempts = await app_state.redis_client.get(attempt_key)
        if attempts and int(attempts) >= 5:
            ttl = await app_state.redis_client.ttl(attempt_key)
            raise HTTPException(
                status_code=429,
                detail=f"Too many login attempts. Try again in {ttl} seconds.",
            )
        await app_state.redis_client.incr(attempt_key)
        await app_state.redis_client.expire(attempt_key, 60)

    ad_user = await authenticate_ad(email, credentials.password)
    if ad_user is None:
        raise HTTPException(status_code=401, detail="AD authentication failed")
    if ad_user.get("_disabled"):
        app_state.logger.info("AD login not configured, falling back to local DB")
        raise HTTPException(status_code=501, detail="AD/LDAP not configured. Use /auth/login instead.")

    if app_state.redis_client:
        await app_state.redis_client.delete(f"login:attempts:{email}")

    if app_state.db_pool:
        async with app_state.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, display_name, role, organization_id, mfa_enabled "
                "FROM users WHERE email = $1", email,
            )
            if row:
                user_id = str(row["id"])
                org_id = str(row["organization_id"]) if row["organization_id"] else ""
                role = ad_user["role"]
                display_name = ad_user["display_name"]
                await conn.execute(
                    "UPDATE users SET role = $1, display_name = $2, last_login = NOW() WHERE id = $3::uuid",
                    role, display_name, user_id,
                )
            else:
                org_id = "00000000-0000-0000-0000-000000000000"
                user_id = str(__import__("uuid").uuid4())
                pwd_hash = hash_password(secrets.token_hex(32))
                await conn.execute(
                    """INSERT INTO users (id, email, password_hash, display_name, role, organization_id,
                       is_active, auth_provider) VALUES ($1, $2, $3, $4, $5, $6::uuid, true, 'ad')""",
                    user_id, email, pwd_hash, ad_user["display_name"], ad_user["role"], org_id,
                )
                display_name = ad_user["display_name"]

            access_token, access_exp = create_access_token(user_id, email, ad_user["role"], org_id)
            refresh_token, refresh_exp = create_refresh_token(user_id)

            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user={
                    "id": user_id,
                    "email": email,
                    "display_name": display_name,
                    "role": ad_user["role"],
                    "organization_id": org_id,
                    "mfa_enabled": False,
                },
            )

    raise HTTPException(status_code=503, detail="Database not available")


@router.post("/api/v1/auth/refresh")
async def refresh_access_token(refresh_token_body: Dict[str, str] = None):
    if not refresh_token_body or "refresh_token" not in refresh_token_body:
        raise HTTPException(status_code=400, detail="refresh_token is required")

    token = refresh_token_body["refresh_token"]

    try:
        payload = decode_token(token)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload["sub"]
    jti = payload["jti"]

    if not app_state.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with app_state.db_pool.acquire() as conn:
        session = await conn.fetchrow(
            """SELECT id FROM user_sessions
               WHERE user_id = $1::uuid AND refresh_token = $2
               AND is_revoked = false AND expires_at > NOW()""",
            user_id, token,
        )
        if not session:
            raise HTTPException(status_code=401, detail="Refresh token has been revoked")

        await conn.execute(
            "UPDATE user_sessions SET is_revoked = true WHERE id = $1",
            session["id"],
        )

    if app_state.redis_client:
        await app_state.redis_client.setex(
            f"{TOKEN_BLACKLIST_PREFIX}{jti}",
            86400 * JWT_REFRESH_TOKEN_EXPIRE_DAYS,
            "revoked",
        )

    async with app_state.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT email, role, organization_id FROM users WHERE id = $1::uuid AND is_active = true",
            user_id,
        )
        if not row:
            raise HTTPException(status_code=401, detail="User account disabled")

    org_id = str(row["organization_id"]) if row.get("organization_id") else ""
    access_token, access_exp = create_access_token(user_id, row["email"], row["role"], org_id)
    refresh_token, refresh_exp = create_refresh_token(user_id)

    async with app_state.db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO user_sessions (user_id, refresh_token, expires_at)
               VALUES ($1, $2, to_timestamp($3))""",
            user_id, refresh_token, refresh_exp,
        )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/api/v1/auth/logout")
async def logout(current_user: AuthContext = Depends(get_current_user)):
    if app_state.redis_client:
        await app_state.redis_client.setex(
            f"{TOKEN_BLACKLIST_PREFIX}{current_user.jti}",
            JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 60,
            "logged_out",
        )
    if app_state.db_pool:
        async with app_state.db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE user_sessions SET is_revoked = true
                   WHERE user_id = $1::uuid AND is_revoked = false""",
                current_user.user_id,
            )
    app_state.logger.info(f"User {current_user.email} logged out, sessions revoked")
    return {"status": "ok", "message": "Logged out successfully"}


@router.get("/api/v1/auth/me")
async def get_current_user_info(current_user: AuthContext = Depends(get_current_user)):
    return {
        "id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role,
        "organization_id": str(current_user.org_id) if current_user.org_id else "",
        "display_name": current_user.email.split("@")[0].capitalize() if current_user.email else "",
    }