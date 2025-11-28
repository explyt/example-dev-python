"""Django-RQ compatibility layer backed by diskcache.

Provides a compatible API for django-rq.
All functionality is delegated to utilities.diskcache_backend.
"""

from .queues import get_queue, get_connection, get_redis_connection, get_queue_by_index  # noqa: F401
from .utils import get_statistics, get_jobs, stop_jobs  # noqa: F401
from .settings import QUEUES_LIST, QUEUES_MAP  # noqa: F401
from .workers import get_worker  # noqa: F401


def job(*dargs, **dkwargs):
    """Decorator for marking functions as jobs (no-op pass-through)."""
    def _wrap(func):
        return func
    return _wrap
