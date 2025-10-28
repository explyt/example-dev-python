from __future__ import annotations
from typing import Any, Dict, Iterable, List
from utilities.diskcache_backend import Queue, _get_queue_statistics


def get_statistics(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Get RQ statistics. Returns a dict with workers, queues, and jobs info."""
    from .settings import QUEUES_LIST, QUEUES_MAP
    
    queues_data = [
        _get_queue_statistics(
            queue_config['name'] if isinstance(queue_config, dict) else queue_config,
            QUEUES_MAP.get(
                queue_config['name'] if isinstance(queue_config, dict) else queue_config,
                i
            )
        )
        for i, queue_config in enumerate(QUEUES_LIST)
    ]
    
    return {
        "workers": 1,
        "queues": queues_data,
        "jobs": sum(q['jobs'] for q in queues_data),
    }


def get_jobs(queue: Queue, job_ids: Iterable[str], registry: Any) -> List[Any]:
    """Get jobs by IDs from queue."""
    return [job for job_id in job_ids if (job := queue.fetch_job(job_id))]


def stop_jobs(queue: Queue, job_id: str):
    return [0]
