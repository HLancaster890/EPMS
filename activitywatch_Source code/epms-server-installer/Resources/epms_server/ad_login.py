"""
AD/LDAP login handler for EPMS Enterprise Server.
Authenticates users against Active Directory via LDAP bind,
auto-provisions users and maps AD groups to EPMS roles.
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger("epms.server.ad")

try:
    import ldap3
    HAS_LDAP = True
except ImportError:
    HAS_LDAP = False

# Environment configuration
LDAP_SERVER = os.environ.get("EPMS_LDAP_SERVER", "")
LDAP_PORT = int(os.environ.get("EPMS_LDAP_PORT", "636"))
LDAP_USE_SSL = os.environ.get("EPMS_LDAP_USE_SSL", "").lower() not in ("0", "false", "no", "")
LDAP_BASE_DN = os.environ.get("EPMS_LDAP_BASE_DN", "dc=example,dc=com")
LDAP_USER_DN = os.environ.get("EPMS_LDAP_USER_DN", "cn=users,cn={base_dn}")
LDAP_BIND_DN = os.environ.get("EPMS_LDAP_BIND_DN", "")
LDAP_BIND_PASSWORD = os.environ.get("EPMS_LDAP_BIND_PASSWORD", "")
LDAP_USER_FILTER = os.environ.get("EPMS_LDAP_USER_FILTER",
    "(&(objectClass=user)(objectCategory=person)(mail={email}))")
LDAP_GROUP_FILTER = os.environ.get("EPMS_LDAP_GROUP_FILTER",
    "(&(objectClass=group)(cn={group_name}))")

# Role mapping: AD group name -> EPMS role
# Override via EPMS_LDAP_ROLE_MAP env var (JSON string)
DEFAULT_ROLE_MAP = {
    "EPMS-Admins": "super_admin",
    "EPMS-Managers": "manager",
    "EPMS-Users": "employee",
    "Domain Admins": "admin",
    "Domain Users": "employee",
}

def _get_role_map() -> Dict[str, str]:
    raw = os.environ.get("EPMS_LDAP_ROLE_MAP", "")
    if raw:
        try:
            import json
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid EPMS_LDAP_ROLE_MAP JSON, using defaults")
    return DEFAULT_ROLE_MAP


async def authenticate_ad(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user against Active Directory via LDAP bind.

    Returns user info dict on success: {email, display_name, username, role, groups}
    Returns None on failed authentication.
    Returns {"_disabled": True} if AD login is not configured.
    """
    if not HAS_LDAP:
        logger.warning("ldap3 not installed — AD/LDAP login unavailable. Install: pip install ldap3")
        return {"_disabled": True}

    if not LDAP_SERVER:
        logger.info("EPMS_LDAP_SERVER not set — AD login disabled")
        return {"_disabled": True}

    server = ldap3.Server(LDAP_SERVER, port=LDAP_PORT, use_ssl=LDAP_USE_SSL,
                          connect_timeout=10, get_info=ldap3.NONE)

    # Phase 1: Bind with service account to search for the user
    try:
        conn = ldap3.Connection(server, user=LDAP_BIND_DN, password=LDAP_BIND_PASSWORD,
                                auto_bind=True, receive_timeout=10)
    except ldap3.core.exceptions.LDAPException as e:
        logger.error(f"AD bind failed with service account: {e}")
        return None

    # Search for user by mail attribute
    search_filter = LDAP_USER_FILTER.replace("{email}", email)
    try:
        conn.search(search_base=LDAP_BASE_DN, search_filter=search_filter,
                    attributes=["cn", "displayName", "mail", "sAMAccountName",
                                "memberOf", "distinguishedName"])
    except ldap3.core.exceptions.LDAPException as e:
        logger.error(f"AD search failed: {e}")
        conn.unbind()
        return None

    if len(conn.entries) == 0:
        logger.info(f"AD user not found: {email}")
        conn.unbind()
        return None

    entry = conn.entries[0]
    user_dn = str(entry.distinguishedName)
    display_name = str(entry.displayName.value if hasattr(entry, "displayName") and entry.displayName else
                       entry.cn.value if hasattr(entry, "cn") and entry.cn else email)
    username = str(entry.sAMAccountName.value if hasattr(entry, "sAMAccountName") and entry.sAMAccountName else "")

    # Collect group memberships
    groups = []
    if hasattr(entry, "memberOf") and entry.memberOf:
        for group_dn in entry.memberOf:
            cn_part = str(group_dn).split(",")[0].replace("CN=", "").replace("cn=", "")
            groups.append(cn_part)

    conn.unbind()

    # Phase 2: Bind with user's credentials to verify password
    try:
        user_conn = ldap3.Connection(server, user=user_dn, password=password,
                                     auto_bind=True, receive_timeout=10)
        user_conn.unbind()
    except ldap3.core.exceptions.LDAPException:
        logger.info(f"AD password verification failed for {email}")
        return None

    # Determine role from group membership
    role_map = _get_role_map()
    role = "employee"
    for group_name in groups:
        mapped_role = role_map.get(group_name)
        if mapped_role:
            role_priority = {"super_admin": 0, "admin": 1, "manager": 2, "employee": 3}
            if role_priority.get(mapped_role, 99) < role_priority.get(role, 99):
                role = mapped_role

    return {
        "email": email,
        "display_name": display_name,
        "username": username,
        "role": role,
        "groups": groups,
    }
