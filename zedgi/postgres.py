"""Postgres client — query, transaction, and custom-hook invocation."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .client import CredentialSelector, Transport


class PostgresClient:
    def __init__(self, transport: Transport, credential: Optional[CredentialSelector] = None) -> None:
        self._t = transport
        self._credential = credential

    def ping(self) -> Dict[str, Any]:
        return self._t.call("postgres", "ping", credential=self._credential)

    def query(self, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Returns ``{"rows": [...], "rowCount": int, "fields": [...]}``."""
        return self._t.call("postgres", "query", {"sql": sql, "params": params or []}, self._credential)

    def transaction(self, statements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Each statement is ``{"sql": str, "params": [...]}`` run in one transaction."""
        return self._t.call("postgres", "transaction", {"statements": statements}, self._credential)

    def hook(self, name: str, *, params: Optional[List[Any]] = None, args: Optional[List[Any]] = None) -> Any:
        """Invoke a registered custom hook (paid tier)."""
        payload: Dict[str, Any] = {}
        if params is not None:
            payload["params"] = params
        if args is not None:
            payload["args"] = args
        return self._t.call("postgres", name, payload, self._credential)
