"""Settings for django_rq backed by diskcache.

These settings are also created in utilities.diskcache_backend._setup_fake_modules()
to ensure availability before Django initialization.
"""

QUEUES_LIST = [
    {"name": "default", "connection_config": {}},
    {"name": "high", "connection_config": {}},
    {"name": "low", "connection_config": {}},
]
QUEUES_MAP = {"default": 0, "high": 1, "low": 2}
