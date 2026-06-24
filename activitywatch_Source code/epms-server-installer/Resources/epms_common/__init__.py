from epms_common.db import create_pool, close_pool, get_db
from epms_common.redis_cache import create_redis, close_redis
from epms_common.middleware import setup_cors