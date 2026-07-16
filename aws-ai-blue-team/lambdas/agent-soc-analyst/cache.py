"""
In-memory TTL cache for enrichment results.
Prevents redundant API calls for the same entity within a 5-minute window.
"""
import time

# Simple dict-based cache with TTL
_cache = {}
_DEFAULT_TTL = 300  # 5 minutes


def get_cached(key):
    """Get a cached value if it exists and hasn't expired."""
    entry = _cache.get(key)
    if entry and time.time() < entry["expires_at"]:
        return entry["data"]
    # Expired or missing
    if entry:
        del _cache[key]
    return None


def set_cached(key, data, ttl=_DEFAULT_TTL):
    """Store a value in the cache with TTL."""
    _cache[key] = {
        "data": data,
        "expires_at": time.time() + ttl,
    }


def clear_cache():
    """Clear the entire cache (for testing)."""
    global _cache
    _cache = {}


def cache_stats():
    """Return cache stats for observability."""
    now = time.time()
    valid = sum(1 for v in _cache.values() if now < v["expires_at"])
    return {"total_entries": len(_cache), "valid_entries": valid}
