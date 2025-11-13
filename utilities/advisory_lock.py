"""Advisory lock implementation.

Provides a no-op advisory lock.
"""


class _NoopLock:
    """Advisory lock shim.

    Behaves both as a context manager (for `with advisory_lock(...)`) and as a
    decorator factory (for `@advisory_lock(...)`).
    """

    def __init__(self, key):
        self.key = key

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper


def advisory_lock(key):
    """Return a lock object.
    
    Behaves both as a context manager (for `with advisory_lock(...)`) and as a
    decorator factory (for `@advisory_lock(...)`).
    
    Args:
        key: Lock key
        
    Returns:
        Lock object (context manager or decorator)
    """
    return _NoopLock(key)
