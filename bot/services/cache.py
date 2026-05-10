"""
Redis Cache Service — GitroHub v2.0
All caching operations. Sub-millisecond reads.
Panel registry, FSM state, API cache, debounce, sessions.
"""
import asyncio
import logging
import time
from typing import Any, Optional

import orjson
import redis.asyncio as aioredis
from config import settings

logger = logging.getLogger(__name__)
_redis: Optional[aioredis.Redis] = None


async def init_redis():
    global _redis
    _redis = await aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        health_check_interval=30,
    )
    await _redis.ping()
    logger.info("✅ Redis connected")


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()


def r() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialized")
    return _redis


# ── Panel Registry ────────────────────────────────────────────────────────────
# Stores chat_id:message_id for each context panel per user
# Key: panel:{telegram_id}:{context}
# Value: "{chat_id}:{message_id}"

async def get_panel(telegram_id: int, context: str) -> Optional[tuple[int, int]]:
    val = await r().get(f"panel:{telegram_id}:{context}")
    if not val:
        return None
    chat_id, msg_id = val.split(":", 1)
    return int(chat_id), int(msg_id)


async def set_panel(telegram_id: int, context: str,
                    chat_id: int, message_id: int):
    await r().set(
        f"panel:{telegram_id}:{context}",
        f"{chat_id}:{message_id}",
        ex=86400  # 24 hours
    )


async def delete_panel(telegram_id: int, context: str):
    await r().delete(f"panel:{telegram_id}:{context}")


async def delete_all_panels(telegram_id: int):
    """Called on logout — wipe all panels."""
    keys = await r().keys(f"panel:{telegram_id}:*")
    if keys:
        await r().delete(*keys)


# ── FSM State ────────────────────────────────────────────────────────────────
# Key: state:{telegram_id}
# Value: JSON {"state": str, "data": dict}

async def get_state(telegram_id: int) -> dict:
    val = await r().get(f"state:{telegram_id}")
    if not val:
        return {"state": "idle", "data": {}}
    return orjson.loads(val)


async def set_state(telegram_id: int, state: str, data: dict = None):
    payload = orjson.dumps({"state": state, "data": data or {}}).decode()
    await r().set(f"state:{telegram_id}", payload, ex=3600)  # 1hr TTL


async def clear_state(telegram_id: int):
    await r().delete(f"state:{telegram_id}")


async def get_state_data(telegram_id: int) -> dict:
    s = await get_state(telegram_id)
    return s.get("data", {})


async def update_state_data(telegram_id: int, **kwargs):
    s = await get_state(telegram_id)
    s["data"].update(kwargs)
    await set_state(telegram_id, s["state"], s["data"])


# ── API Cache ─────────────────────────────────────────────────────────────────
# Key: cache:{telegram_id}:{key}
# Value: JSON serialized data

async def cache_get(telegram_id: int, key: str) -> Optional[Any]:
    val = await r().get(f"cache:{telegram_id}:{key}")
    if val is None:
        return None
    return orjson.loads(val)


async def cache_set(telegram_id: int, key: str, value: Any, ttl: int):
    payload = orjson.dumps(value).decode()
    await r().set(f"cache:{telegram_id}:{key}", payload, ex=ttl)


async def cache_delete(telegram_id: int, key: str):
    await r().delete(f"cache:{telegram_id}:{key}")


async def cache_delete_pattern(telegram_id: int, pattern: str):
    """Delete all cache keys matching pattern for a user."""
    keys = await r().keys(f"cache:{telegram_id}:{pattern}*")
    if keys:
        await r().delete(*keys)


async def invalidate_repo_cache(telegram_id: int, repo_name: str = None):
    """Invalidate repo-related caches after mutation."""
    if repo_name:
        await cache_delete_pattern(telegram_id, f"repo:{repo_name}")
    await cache_delete_pattern(telegram_id, "repos:")
    await cache_delete_pattern(telegram_id, "forks:")


# ── Debounce ──────────────────────────────────────────────────────────────────
# Prevents spam from rapid button taps
# Key: debounce:{telegram_id}

async def check_debounce(telegram_id: int) -> bool:
    """Returns True if action is allowed (not debounced)."""
    key = f"debounce:{telegram_id}"
    now = time.time()
    last = await r().get(key)
    if last and (now - float(last)) < (settings.debounce_ms / 1000):
        return False
    await r().set(key, str(now), px=settings.debounce_ms)
    return True


# ── OAuth State ───────────────────────────────────────────────────────────────
# Stores pending OAuth states with CSRF protection
# Key: oauth:{state}

async def store_oauth_state(state: str, telegram_id: int):
    await r().set(
        f"oauth:{state}",
        str(telegram_id),
        ex=600  # 10 minutes
    )


async def consume_oauth_state(state: str) -> Optional[int]:
    """Get and delete OAuth state (one-time use)."""
    key = f"oauth:{state}"
    val = await r().get(key)
    if val:
        await r().delete(key)
        return int(val)
    return None


# ── Rate limit tracking ───────────────────────────────────────────────────────

async def store_rate_limit(telegram_id: int, remaining: int,
                           limit: int, reset_timestamp: float):
    data = {"remaining": remaining, "limit": limit, "reset": reset_timestamp}
    await r().set(
        f"ratelimit:{telegram_id}",
        orjson.dumps(data).decode(),
        ex=settings.ttl_rate_limit
    )


async def get_rate_limit(telegram_id: int) -> Optional[dict]:
    val = await r().get(f"ratelimit:{telegram_id}")
    return orjson.loads(val) if val else None


# ── Notification webhook buffer ───────────────────────────────────────────────
# Buffers incoming GitHub webhooks for processing

async def push_webhook_event(payload: dict):
    await r().lpush("webhook_queue", orjson.dumps(payload).decode())


async def pop_webhook_event() -> Optional[dict]:
    val = await r().rpop("webhook_queue")
    return orjson.loads(val) if val else None


async def get_queue_length() -> int:
    return await r().llen("webhook_queue")


# ── System metrics cache ──────────────────────────────────────────────────────

async def store_metrics(metrics: dict):
    await r().set("metrics:system", orjson.dumps(metrics).decode(), ex=30)


async def get_metrics() -> Optional[dict]:
    val = await r().get("metrics:system")
    return orjson.loads(val) if val else None


# ── Full user wipe (logout) ───────────────────────────────────────────────────

async def wipe_user(telegram_id: int):
    """
    Complete wipe of all Redis data for a user.
    Called on disconnect/logout.
    """
    patterns = [
        f"panel:{telegram_id}:*",
        f"state:{telegram_id}",
        f"cache:{telegram_id}:*",
        f"debounce:{telegram_id}",
        f"ratelimit:{telegram_id}",
    ]
    for pattern in patterns:
        if "*" in pattern:
            keys = await r().keys(pattern)
            if keys:
                await r().delete(*keys)
        else:
            await r().delete(pattern)
    logger.info(f"🗑️ Redis data wiped for user {telegram_id}")


# ── Health check ──────────────────────────────────────────────────────────────

async def redis_ping() -> bool:
    try:
        return await r().ping()
    except Exception:
        return False


async def redis_info() -> dict:
    try:
        info = await r().info("memory")
        return {
            "used_memory": info.get("used_memory_human", "?"),
            "peak_memory": info.get("used_memory_peak_human", "?"),
        }
    except Exception:
        return {}
