"""Redis client — built-in commands plus custom-hook invocation."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .client import Transport


class RedisClient:
    def __init__(self, transport: Transport) -> None:
        self._t = transport

    def _call(self, method: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        return self._t.call("redis", method, payload or {})

    # ── Common built-ins ──────────────────────────────────────────────
    def ping(self) -> str:
        return self._call("ping")

    def get(self, key: str) -> Optional[str]:
        return self._call("get", {"args": [key]})

    def set(self, key: str, value: str, *args: Any) -> Any:
        return self._call("set", {"args": [key, value, *args]})

    def delete(self, *keys: str) -> int:
        return self._call("del", {"args": list(keys)})

    def incr(self, key: str) -> int:
        return self._call("incr", {"args": [key]})

    def expire(self, key: str, seconds: int) -> int:
        return self._call("expire", {"args": [key, seconds]})

    def hget(self, key: str, field: str) -> Optional[str]:
        return self._call("hget", {"args": [key, field]})

    def hgetall(self, key: str) -> Optional[Dict[str, str]]:
        return self._call("hgetall", {"args": [key]})

    def lrange(self, key: str, start: int, stop: int) -> List[str]:
        return self._call("lrange", {"args": [key, start, stop]})

    def call(self, command: str, *args: Any) -> Any:
        """Escape hatch for any Redis command not exposed as a named method."""
        return self._call("call", {"command": command, "args": list(args)})

    # ── Custom hooks ──────────────────────────────────────────────────
    def hook(
        self,
        name: str,
        *,
        keys: Optional[List[str]] = None,
        args: Optional[List[Any]] = None,
    ) -> Any:
        """Invoke a registered custom hook (paid tier).

        ``keys`` maps to Lua ``KEYS``; ``args`` maps to ``ARGV`` / macro substitution.
        """
        payload: Dict[str, Any] = {}
        if keys is not None:
            payload["keys"] = keys
        if args is not None:
            payload["args"] = args
        return self._call(name, payload)
