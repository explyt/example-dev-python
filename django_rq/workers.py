"""Worker utilities for django_rq backed by diskcache."""

from __future__ import annotations
from typing import Any
from utilities.diskcache_backend import Worker, get_worker as _get_worker


def get_worker(queue_name: str = "default", name: Any = None, **kwargs: Any) -> Worker:
    """Get a worker for the specified queue."""
    return _get_worker(queue_name, name, **kwargs)
