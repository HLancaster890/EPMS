"""
Shared application configuration.
Centralizes JWT settings, prefixes, and connection references
shared across modules (rbac, aggregation, main service).
"""

import os
import secrets

JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "15"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("JWT_REFRESH_EXPIRE_DAYS", "7"))
TOKEN_BLACKLIST_PREFIX = "token:blacklist:"
AGENT_RATELIMIT_PREFIX = "agent:ratelimit:"
AGENT_RATELIMIT_PER_MINUTE = 60
ENROLLMENT_MODE = "enrollment"
PASSWORD_HASH_ITERATIONS = 600000

# Mutable reference — set by epms_server_service at startup
redis_client = None
