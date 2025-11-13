"""Diskcache-based backend for caching and job queues.

Provides persistent, thread-safe storage using diskcache.
Creates compatibility shims for rq and django_rq modules.
"""

from __future__ import annotations

import uuid
import os
import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from pathlib import Path

import diskcache

# Setup logger
logger = logging.getLogger(__name__)

# Global shared diskcache instances per process
_CACHE_DIR = Path(os.environ.get('DISKCACHE_DIR', '/tmp/netbox_cache'))
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Main cache instance
_cache = diskcache.Cache(str(_CACHE_DIR / 'main'))


class CacheConnection:
    """Wrapper around diskcache.Cache with additional methods."""
    def __init__(self, cache):
        self._cache = cache
    
    def flushall(self):
        """Clear all queues, registries and cache."""
        for queue in _QUEUES.values():
            queue._jobs.clear()
            queue._deque.clear()
        
        for index in _REGISTRIES.values():
            index.clear()
        _REGISTRIES.clear()
        
        self._cache.clear()
    
    def __getattr__(self, name):
        """Proxy all other methods to the underlying cache."""
        return getattr(self._cache, name)


# Create connection wrapper
_connection = CacheConnection(_cache)


class Queue:
    """Queue implementation using diskcache.Deque for persistence."""
    
    def __init__(self, name: str = "default") -> None:
        self.name = name
        self._jobs: Dict[str, Job] = {}  # In-memory job storage
        self.connection = _connection
        self.serializer = None
        self._deque = diskcache.Deque(directory=str(_CACHE_DIR / f'queue_{name}'))

    @property
    def jobs(self) -> List[Job]:
        """Return jobs in FIFO order."""
        return [self._jobs[job_id] for job_id in self._deque if job_id in self._jobs]

    @property
    def count(self) -> int:
        return len(self._jobs)

    def enqueue(self, func: Any, *args: Any, **kwargs: Any) -> Job:
        depends_on = kwargs.pop('depends_on', None)
        job_id = kwargs.pop('job_id', None) or uuid.uuid4().hex
        
        job = Job(id=job_id, connection=self.connection, origin=self.name, func=func)
        job.args = args
        job.kwargs = kwargs
        job.set_status(JobStatus.DEFERRED if depends_on else JobStatus.QUEUED, persist=False)
        
        self._jobs[job.id] = job
        self._deque.append(job.id)
        
        logger.info(f"Job {job.id} enqueued to queue {self.name}: {func}")
        
        return job

    def enqueue_at(self, schedule_at: Any, func: Any, *args: Any, **kwargs: Any) -> Job:
        """Schedule a job to run at a specific time."""
        job = self.enqueue(func, *args, **kwargs)
        job.scheduled_at = schedule_at
        scheduled_registry = ScheduledJobRegistry(self.name, connection=self.connection)
        scheduled_registry.add(job)
        return job

    def fetch_job(self, job_id: str) -> Optional[Job]:
        """Fetch a job by ID."""
        return self._jobs.get(job_id)

    @property
    def job_ids(self) -> List[str]:
        """Get list of job IDs."""
        return list(self._jobs.keys())

    def empty(self) -> None:
        """Clear all jobs."""
        self._jobs.clear()
        self._deque.clear()

    def get_jobs(self) -> List[Job]:
        """Compatibility method."""
        return self.jobs


# Global queues registry
_QUEUES: Dict[str, Queue] = {}


def get_queue(name: str = "default") -> Queue:
    """Get or create a queue by name (singleton pattern)."""
    if name not in _QUEUES:
        _QUEUES[name] = Queue(name)
    return _QUEUES[name]


def get_worker(queue_name: str = "default", name: Optional[str] = None, **kwargs) -> 'Worker':
    """Get or create a worker for the given queue."""
    queue = get_queue(queue_name)
    worker_name = name or queue_name
    worker_key = f'rq:worker:{worker_name}'
    if worker_key not in _WORKERS:
        worker = Worker([queue], name=worker_name)
        _WORKERS[worker_key] = worker
    else:
        worker = _WORKERS[worker_key]
    return worker


# Global workers registry
_WORKERS: Dict[str, 'Worker'] = {}


class Worker:
    """Worker for executing jobs from queues."""
    
    def __init__(self, queues: Iterable[Queue], name: Optional[str] = None, connection: Any = None):
        self.queues = list(queues)
        self.name = name or uuid.uuid4().hex
        self.connection = connection or _connection
        self.birth_date = None
        self.key = f'rq:worker:{self.name}'
        self.total_working_time = 0
        self._current_job = None
        self.state = 'idle'
        self.successful_job_count = 0
        self.failed_job_count = 0
        self.pid = str(uuid.uuid4().int)[:5]
        _WORKERS[self.key] = self

    def work(self, *args: Any, **kwargs: Any) -> None:
        """Execute jobs from the queue if burst=True."""
        if not kwargs.get('burst', False):
            return
        
        logger.info(f"Worker {self.name} starting to process jobs")
        
        for queue in self.queues:
            logger.info(f"Processing queue: {queue.name}")
            for job in list(queue.jobs):
                try:
                    logger.info(f"Executing job {job.id}: {job.func}")
                    if callable(job.func):
                        job.result = job.func(*job.args, **job.kwargs)
                    job.set_status(JobStatus.FINISHED)
                    logger.info(f"Job {job.id} completed successfully")
                except Exception as e:
                    logger.error(f"Job {job.id} failed with error: {e}", exc_info=True)
                    job.exc_info = str(e)
                    job.set_status(JobStatus.FAILED)
        
        logger.info(f"Worker {self.name} finished processing jobs")

    def register_birth(self) -> None:
        self.birth_date = datetime.now()

    def prepare_job_execution(self, job: Any, remove_from_intermediate_queue: bool = False) -> None:
        job.set_status(JobStatus.STARTED)
        started_registry = StartedJobRegistry(job.origin, connection=self.connection)
        started_registry.add(job)

    def prepare_execution(self, job: Any) -> None:
        self.prepare_job_execution(job)

    def monitor_work_horse(self, job: Any, queue: Any) -> None:
        job.set_status(JobStatus.FAILED)
        started_registry = StartedJobRegistry(queue.name, connection=queue.connection)
        started_registry.remove(job.id)
        failed_registry = FailedJobRegistry(queue.name, connection=queue.connection)
        failed_registry.add(job.id)

    @staticmethod
    def count(connection: Any = None, queue: Any = None) -> int:
        return len(_WORKERS)
    
    @staticmethod
    def all(connection: Any = None) -> List['Worker']:
        return list(_WORKERS.values())
    
    @staticmethod
    def find_by_key(key: str, connection: Any = None) -> Optional['Worker']:
        return _WORKERS.get(key)
    
    def queue_names(self) -> List[str]:
        return [queue.name for queue in self.queues]
    
    def get_current_job(self) -> Optional['Job']:
        return self._current_job
    
    def get_state(self) -> str:
        return self.state
    
    def set_state(self, state: str) -> None:
        self.state = state


# Connection helpers
def get_connection(*args: Any, **kwargs: Any):
    """Return a diskcache connection-compatible object."""
    return _connection


def get_redis_connection(*args: Any, **kwargs: Any):
    """Compatibility alias for get_connection."""
    return _connection


# Job exceptions
class InvalidJobOperation(Exception):
    """Raised when an invalid operation is performed on a job."""
    pass


class NoSuchJobError(Exception):
    """Raised when a job does not exist."""
    pass


# Job status constants
class JobStatus:
    """Job status constants."""
    QUEUED = 'queued'
    STARTED = 'started'
    FINISHED = 'finished'
    FAILED = 'failed'
    DEFERRED = 'deferred'
    SCHEDULED = 'scheduled'
    STOPPED = 'stopped'
    CANCELED = 'canceled'
    
    # Aliases for compatibility
    STATUS_QUEUED = 'queued'
    STATUS_STARTED = 'started'
    STATUS_FINISHED = 'finished'
    STATUS_FAILED = 'failed'
    STATUS_DEFERRED = 'deferred'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_STOPPED = 'stopped'
    STATUS_CANCELED = 'canceled'


# Job implementation
class Job:
    """Job implementation for task queue."""
    
    def __init__(self, id=None, connection=None, origin=None, func=None):
        self.id = id or uuid.uuid4().hex
        self.connection = connection
        self.origin = origin or 'default'
        self.status = JobStatus.QUEUED
        self.created_at = datetime.now()
        self.enqueued_at = None
        self.started_at = None
        self.ended_at = None
        self.result = None
        self.exc_info = None
        self.func = func
        
        # Build func_name
        if func:
            module = getattr(func, '__module__', '')
            qualname = getattr(func, '__qualname__', getattr(func, '__name__', str(func)))
            self.func_name = f"{module}.{qualname}()" if module else f"{qualname}()"
            self.description = f"{module}.{qualname}" if module else qualname
        else:
            self.func_name = 'unknown'
            self.description = 'unknown'
        
        self.args = ()
        self.kwargs = {}
        self.serializer = None
        self._exc_info = None
        self._dependency_id = None
        self.timeout = -1
        self.result_ttl = -1
        self.worker_name = ''
        self.meta = {}
        self.last_heartbeat = ''

    def get_status(self):
        return self.status

    def set_status(self, status, persist=True):
        """Set job status."""
        self.status = status
        now = datetime.now()
        if status == JobStatus.QUEUED:
            self.enqueued_at = now
        elif status == JobStatus.STARTED:
            self.started_at = now
        elif status in (JobStatus.FINISHED, JobStatus.FAILED, JobStatus.STOPPED, JobStatus.CANCELED):
            self.ended_at = now
    
    def get_position(self):
        return -1

    @property
    def is_failed(self):
        return self.status == JobStatus.FAILED
    
    @property
    def is_finished(self):
        return self.status == JobStatus.FINISHED
    
    @property
    def is_queued(self):
        return self.status == JobStatus.QUEUED
    
    @property
    def is_started(self):
        return self.status == JobStatus.STARTED
    
    @property
    def is_deferred(self):
        return self.status == JobStatus.DEFERRED
    
    @property
    def is_canceled(self):
        return self.status == JobStatus.CANCELED
    
    @property
    def is_scheduled(self):
        return self.status == JobStatus.SCHEDULED
    
    @property
    def is_stopped(self):
        return self.status == JobStatus.STOPPED

    @staticmethod
    def fetch(job_id, connection=None):
        """Fetch a job by ID from queues."""
        for queue in _QUEUES.values():
            job = queue.fetch_job(job_id)
            if job:
                return job
        return None

    @staticmethod
    def exists(job_id, connection=None):
        """Check if job exists."""
        for queue in _QUEUES.values():
            if job_id in queue._jobs:
                return True
        return False


# Global registries storage
_REGISTRIES: Dict[str, diskcache.Index] = {}


# Registry implementations
class BaseRegistry:
    """Base registry using diskcache.Index for persistence."""
    
    def __init__(self, name='default', connection=None):
        self.name = name
        self.connection = connection
        registry_type = self.__class__.__name__
        registry_key = f'{registry_type}:{name}'
        
        if registry_key not in _REGISTRIES:
            index_dir = _CACHE_DIR / 'registries' / registry_key
            index_dir.mkdir(parents=True, exist_ok=True)
            _REGISTRIES[registry_key] = diskcache.Index(str(index_dir))
        
        self._index = _REGISTRIES[registry_key]

    def get_job_ids(self):
        """Get all job IDs from the registry."""
        return list(self._index.keys())

    def add(self, job_or_id, ttl: int = -1):
        """Add a job ID to the registry."""
        job_id = job_or_id.id if hasattr(job_or_id, 'id') else str(job_or_id)
        self._index[job_id] = True

    def remove(self, job_id: str):
        """Remove a job ID from the registry."""
        if job_id in self._index:
            del self._index[job_id]

    def __len__(self):
        return len(self._index)

    def __contains__(self, job_id: str):
        return job_id in self._index


class FailedJobRegistry(BaseRegistry):
    pass


class StartedJobRegistry(BaseRegistry):
    pass


class FinishedJobRegistry(BaseRegistry):
    pass


class DeferredJobRegistry(BaseRegistry):
    pass


class ScheduledJobRegistry(BaseRegistry):
    def get_scheduled_time(self, job):
        return getattr(job, 'scheduled_at', None)


class CanceledJobRegistry(BaseRegistry):
    pass


# Job timeout exception
class JobTimeoutException(Exception):
    """Raised when a job times out."""
    pass


def clean_worker_registry(connection=None):
    """Clean worker registry (no-op)."""
    pass


def job(*dargs: Any, **dkwargs: Any):
    """Decorator for marking functions as jobs (no-op pass-through)."""
    def _wrap(func):
        return func
    return _wrap


def _get_queue_statistics(queue_name: str, queue_index: int) -> Dict[str, Any]:
    """Get statistics for a single queue."""
    queue = get_queue(queue_name)
    conn = queue.connection
    
    registries = {
        'finished_jobs': len(FinishedJobRegistry(queue_name, connection=conn)),
        'failed_jobs': len(FailedJobRegistry(queue_name, connection=conn)),
        'started_jobs': len(StartedJobRegistry(queue_name, connection=conn)),
        'deferred_jobs': len(DeferredJobRegistry(queue_name, connection=conn)),
        'scheduled_jobs': len(ScheduledJobRegistry(queue_name, connection=conn)),
        'canceled_jobs': len(CanceledJobRegistry(queue_name, connection=conn)),
    }
    
    return {
        'name': queue_name,
        'jobs': queue.count,
        'index': queue_index,
        'oldest_job_timestamp': '',
        'scheduler_pid': '',
        'workers': 0,
        **registries,
    }


def _setup_fake_modules():
    """Create compatibility shims for rq and django_rq modules."""
    import sys
    import types
    
    # Create rq package
    rq_module = types.ModuleType('rq')
    rq_module.Worker = Worker
    rq_module.Retry = lambda *args, **kwargs: None
    sys.modules['rq'] = rq_module
    
    # Create rq submodules
    rq_worker_module = types.ModuleType('rq.worker')
    rq_worker_module.Worker = Worker
    sys.modules['rq.worker'] = rq_worker_module
    
    rq_exceptions_module = types.ModuleType('rq.exceptions')
    rq_exceptions_module.InvalidJobOperation = InvalidJobOperation
    rq_exceptions_module.NoSuchJobError = NoSuchJobError
    sys.modules['rq.exceptions'] = rq_exceptions_module
    
    rq_job_module = types.ModuleType('rq.job')
    rq_job_module.Job = Job
    rq_job_module.JobStatus = JobStatus
    sys.modules['rq.job'] = rq_job_module
    
    rq_registry_module = types.ModuleType('rq.registry')
    rq_registry_module.FailedJobRegistry = FailedJobRegistry
    rq_registry_module.StartedJobRegistry = StartedJobRegistry
    rq_registry_module.FinishedJobRegistry = FinishedJobRegistry
    rq_registry_module.DeferredJobRegistry = DeferredJobRegistry
    rq_registry_module.ScheduledJobRegistry = ScheduledJobRegistry
    rq_registry_module.CanceledJobRegistry = CanceledJobRegistry
    sys.modules['rq.registry'] = rq_registry_module
    
    rq_timeouts_module = types.ModuleType('rq.timeouts')
    rq_timeouts_module.JobTimeoutException = JobTimeoutException
    sys.modules['rq.timeouts'] = rq_timeouts_module
    
    rq_worker_registration_module = types.ModuleType('rq.worker_registration')
    rq_worker_registration_module.clean_worker_registry = clean_worker_registry
    sys.modules['rq.worker_registration'] = rq_worker_registration_module
    
    # Create django_rq package
    django_rq_module = types.ModuleType('django_rq')
    django_rq_module.get_queue = get_queue
    django_rq_module.get_connection = get_connection
    django_rq_module.get_redis_connection = get_redis_connection
    django_rq_module.job = lambda *args, **kwargs: lambda func: func
    sys.modules['django_rq'] = django_rq_module
    
    # Create django_rq submodules
    django_rq_workers_module = types.ModuleType('django_rq.workers')
    django_rq_workers_module.get_worker = get_worker
    sys.modules['django_rq.workers'] = django_rq_workers_module
    
    django_rq_queues_module = types.ModuleType('django_rq.queues')
    django_rq_queues_module.get_connection = get_connection
    django_rq_queues_module.get_redis_connection = get_redis_connection
    django_rq_queues_module.get_queue_by_index = lambda index: get_queue(
        {0: 'default', 1: 'high', 2: 'low'}.get(index, 'default')
    )
    sys.modules['django_rq.queues'] = django_rq_queues_module
    
    # Create django_rq.settings submodule
    django_rq_settings_module = types.ModuleType('django_rq.settings')
    django_rq_settings_module.QUEUES_LIST = [
        {'name': 'default', 'connection_config': {}},
        {'name': 'high', 'connection_config': {}},
        {'name': 'low', 'connection_config': {}},
    ]
    django_rq_settings_module.QUEUES_MAP = {'default': 0, 'high': 1, 'low': 2}
    sys.modules['django_rq.settings'] = django_rq_settings_module
    
    # Create django_rq.utils submodule
    django_rq_utils_module = types.ModuleType('django_rq.utils')
    
    def _get_statistics(*args, **kwargs):
        queues_data = [
            _get_queue_statistics(
                queue_config['name'],
                django_rq_settings_module.QUEUES_MAP.get(queue_config['name'], i)
            )
            for i, queue_config in enumerate(django_rq_settings_module.QUEUES_LIST)
        ]
        return {
            'workers': 1,
            'queues': queues_data,
            'jobs': sum(q['jobs'] for q in queues_data),
        }
    
    django_rq_utils_module.get_statistics = _get_statistics
    django_rq_utils_module.get_jobs = lambda queue, job_ids, registry: [
        job for job_id in job_ids if (job := queue.fetch_job(job_id))
    ]
    django_rq_utils_module.stop_jobs = lambda queue, job_id: [0]
    sys.modules['django_rq.utils'] = django_rq_utils_module


# Initialize compatibility modules on import
_setup_fake_modules()
