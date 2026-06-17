import os
import logging
import redis

# Configure a basic logger for Redis connection issues
logger = logging.getLogger(__name__)

_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    redis_host = os.getenv('REDIS_HOST')
    redis_port = os.getenv('REDIS_PORT', 10371)
    redis_password = os.getenv('REDIS_PASSWORD')
    redis_username = os.getenv('REDIS_USERNAME', 'default')

    if not redis_host:
        logger.warning("Redis host not configured in environment variables. Redis features will be disabled.")
        return None

    try:
        # Create a StrictRedis client with decode_responses to handle strings natively
        client = redis.Redis(
            host=redis_host,
            port=int(redis_port),
            username=redis_username,
            password=redis_password,
            decode_responses=True,
            socket_connect_timeout=3, # Fail fast if Redis is down
            socket_timeout=3
        )
        # Ping to test connection
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}. Falling back to default database behavior.")
        return None
