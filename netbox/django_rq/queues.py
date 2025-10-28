"""Django-RQ compatibility layer for diskcache backend."""

from __future__ import annotations

from utilities.diskcache_backend import (
    get_queue,
    get_connection,
    get_redis_connection,
)

__all__ = ['get_queue', 'get_connection', 'get_redis_connection', 'get_queue_by_index']


def get_queue_by_index(index: int):
    """Get a queue by index (0=default, 1=high, 2=low)."""
    queue_names = {0: "default", 1: "high", 2: "low"}
    return get_queue(queue_names.get(index, "default"))
