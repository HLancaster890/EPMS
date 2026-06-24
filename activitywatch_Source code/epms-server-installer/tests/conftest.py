import asyncio
import os
import sys
from typing import Any, AsyncGenerator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES_DIR = os.path.join(PROJECT_ROOT, "Resources")
SERVICES_DIR = os.path.join(RESOURCES_DIR, "services")
sys.path.insert(0, SERVICES_DIR)
sys.path.insert(0, RESOURCES_DIR)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_asyncpg_pool():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    conn.prepare = AsyncMock()
    prepared = AsyncMock()
    prepared.fetch = AsyncMock(return_value=[])
    prepared.fetchrow = AsyncMock(return_value=None)
    conn.prepare.return_value = prepared
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=cm)
    return pool


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock(return_value=True)
    r.setex = AsyncMock(return_value=True)
    r.delete = AsyncMock(return_value=True)
    r.exists = AsyncMock(return_value=False)
    r.keys = AsyncMock(return_value=[])
    r.ping = AsyncMock(return_value=True)
    return r



