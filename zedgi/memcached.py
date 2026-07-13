"""Memcached client — beta key/value operations."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .client import CredentialSelector, Transport


class MemcachedClient:
    def __init__(self, transport: Transport, credential: Optional[CredentialSelector] = None) -> None:
        self._t = transport
        self._credential = credential

    def _call(self, method: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        return self._t.call("memcached", method, payload or {}, self._credential)

    def ping(self) -> Dict[str, Any]:
        return self._call("ping")

    def version(self) -> str:
        return self._call("version")

    def get(self, key: str) -> Optional[str]:
        return self._call("get", {"key": key})

    def get_many(self, keys: list[str]) -> Dict[str, Optional[str]]:
        return self._call("get", {"keys": keys})

    def gets(self, key: str) -> Optional[Dict[str, Any]]:
        return self._call("gets", {"key": key})

    def gat(self, ttl: int, key: str) -> Optional[str]:
        return self._call("gat", {"ttl": ttl, "key": key})

    def gats(self, ttl: int, key: str) -> Optional[Dict[str, Any]]:
        return self._call("gats", {"ttl": ttl, "key": key})

    def set(self, key: str, value: Any, ttl: int = 0, flags: int = 0) -> bool:
        return self._call("set", {"key": key, "value": value, "ttl": ttl, "flags": flags})

    def add(self, key: str, value: Any, ttl: int = 0, flags: int = 0) -> bool:
        return self._call("add", {"key": key, "value": value, "ttl": ttl, "flags": flags})

    def replace(self, key: str, value: Any, ttl: int = 0, flags: int = 0) -> bool:
        return self._call("replace", {"key": key, "value": value, "ttl": ttl, "flags": flags})

    def append(self, key: str, value: Any) -> bool:
        return self._call("append", {"key": key, "value": value})

    def prepend(self, key: str, value: Any) -> bool:
        return self._call("prepend", {"key": key, "value": value})

    def cas(self, key: str, value: Any, cas: str, ttl: int = 0, flags: int = 0) -> bool:
        return self._call("cas", {"key": key, "value": value, "cas": cas, "ttl": ttl, "flags": flags})

    def delete(self, key: str) -> bool:
        return self._call("delete", {"key": key})

    def del_(self, key: str) -> bool:
        return self.delete(key)

    def incr(self, key: str, delta: int = 1) -> Optional[int]:
        return self._call("incr", {"key": key, "delta": delta})

    def decr(self, key: str, delta: int = 1) -> Optional[int]:
        return self._call("decr", {"key": key, "delta": delta})

    def touch(self, key: str, ttl: int) -> bool:
        return self._call("touch", {"key": key, "ttl": ttl})

    def stats(self, arg: Optional[str] = None) -> Dict[str, str]:
        return self._call("stats", {"arg": arg} if arg else {})
