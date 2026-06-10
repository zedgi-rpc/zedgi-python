"""MySQL client — query, transaction, and custom-hook invocation."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .client import Transport


class MySQLClient:
    def __init__(self, transport: Transport) -> None:
        self._t = transport

    def ping(self) -> Dict[str, Any]:
        return self._t.call("mysql", "ping")

    def query(self, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Returns ``{"rows": [...], "fields": [...]}``."""
        return self._t.call("mysql", "query", {"sql": sql, "params": params or []})

    def transaction(self, statements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Each statement is ``{"sql": str, "params": [...]}`` run in one transaction."""
        return self._t.call("mysql", "transaction", {"statements": statements})

    def hook(self, name: str, *, params: Optional[List[Any]] = None, args: Optional[List[Any]] = None) -> Any:
        """Invoke a registered custom hook (paid tier)."""
        payload: Dict[str, Any] = {}
        if params is not None:
            payload["params"] = params
        if args is not None:
            payload["args"] = args
        return self._t.call("mysql", name, payload)
