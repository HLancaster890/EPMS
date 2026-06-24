import os, logging
from hmac import compare_digest
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger("epms.common.middleware")

_INTERNAL_API_KEY_WARNED = False

def setup_cors(app: FastAPI, origins: str = "*"):
    cors_list = [o.strip() for o in origins.split(",") if o.strip()]
    use_credentials = cors_list != ["*"]
    if not use_credentials:
        logger.warning("CORS allow_origins=[\"*\"] - credentials disabled. Set explicit origins in config for credentials.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_list,
        allow_credentials=use_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

INTERNAL_API_KEY = os.environ.get("EPMS_INTERNAL_API_KEY", "")

def require_internal_api_key():
    global _INTERNAL_API_KEY_WARNED
    if not INTERNAL_API_KEY:
        logger.critical(
            "EPMS_INTERNAL_API_KEY is not set! Service-to-service auth is DISABLED. "
            "Set this environment variable to a strong random secret in production."
        )
        if not _INTERNAL_API_KEY_WARNED:
            _INTERNAL_API_KEY_WARNED = True
        return
    logger.info("Internal API key configured.")

async def verify_internal_api_key(authorization: str = Header(None)):
    if not INTERNAL_API_KEY:
        logger.warning("verify_internal_api_key called but EPMS_INTERNAL_API_KEY is empty - allowing")
        return True
    if not authorization:
        raise HTTPException(401, "Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not compare_digest(token, INTERNAL_API_KEY):
        raise HTTPException(401, "Invalid API key")
    return True

def health_response(service: str, db_ok: bool = False, redis_ok: bool = False):
    from datetime import datetime, timezone
    return JSONResponse({
        "status": "healthy",
        "service": service,
        "database": "connected" if db_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })