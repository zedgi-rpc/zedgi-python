"""BullMQ queue client — rides on your existing Redis service.

There is no separate service to register: each op is sent as the redis service's
``bull:<method>`` with the queue name in ``payload.target``. The backend runs the
real BullMQ operation (default ``bull`` key prefix, so jobs interoperate with your
own workers).

    queue = zedgi.queue("emails")
    queue.add("send", {"to": "dev@example.com"}, {"attempts": 3})
    queue.get_job_counts()
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .client import CredentialSelector, Transport


class Queue:
    def __init__(self, transport: Transport, name: str, credential: Optional[CredentialSelector] = None) -> None:
        self._t = transport
        self._name = name
        self._credential = credential

    def _call(self, op: str, args: Optional[List[Any]] = None) -> Any:
        return self._t.call("redis", f"bull:{op}", {"target": self._name, "args": args or []}, self._credential)

    # ── Produce ───────────────────────────────────────────────────────
    def add(self, job_name: str, data: Any = None, opts: Optional[Dict[str, Any]] = None) -> Any:
        return self._call("add", [job_name, data, opts])

    # ── Inspect ───────────────────────────────────────────────────────
    def get_job(self, job_id: str) -> Any:
        return self._call("getJob", [job_id])

    def get_jobs(
        self,
        states: Optional[List[str]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        asc: Optional[bool] = None,
    ) -> Any:
        return self._call("getJobs", [states, start, end, asc])

    def get_job_counts(self, *types: str) -> Dict[str, int]:
        return self._call("getJobCounts", list(types))

    def count(self) -> int:
        return self._call("count")

    # Monitor ops are routed to the backend's queue-monitor service, which reads
    # the queue name from args[0] (not payload.target). getSnapshot covers all
    # queues, so it takes no name.
    def get_snapshot(self) -> Any:
        return self._call("getSnapshot")

    def get_events(self) -> Any:
        return self._call("getEvents", [self._name])

    def get_recent_jobs_for_queue(self, limit: Optional[int] = None) -> Any:
        return self._call("getRecentJobsForQueue", [self._name, limit])

    # ── Manage ────────────────────────────────────────────────────────
    def pause(self) -> bool:
        return self._call("pause")

    def resume(self) -> bool:
        return self._call("resume")

    def drain(self, delayed: Optional[bool] = None) -> bool:
        return self._call("drain", [delayed])

    def clean(self, grace: int, limit: int, job_type: str = "completed") -> Any:
        return self._call("clean", [grace, limit, job_type])

    def remove_job(self, job_id: str) -> bool:
        return self._call("removeJob", [job_id])

    def retry_job(self, job_id: str) -> Any:
        return self._call("retryJob", [job_id])

    def promote_job(self, job_id: str) -> Any:
        return self._call("promoteJob", [job_id])

    def obliterate(self, opts: Optional[Dict[str, Any]] = None) -> bool:
        return self._call("obliterate", [opts])

    def close_queue(self) -> bool:
        return self._call("closeQueue")
