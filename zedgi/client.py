"""Low-level HTTP client for the Zedgi RPC endpoint.

Uses only the Python standard library (``urllib``) — zero runtime dependencies,
so it works in any environment (scripts, Lambda, Django, FastAPI, …).
"""
from __future__ import annotations

import json
import uuid
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class RpcError(Exception):
    """Raised when the Zedgi API returns an error envelope."""

    def __init__(self, message: str, code: str = "ZEDGI_ERROR", status: int = 0, details: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details


class Transport:
    """Holds connection options and performs the raw ``POST /rpc`` call."""

    def __init__(self, url: str, key: str, timeout: float = 10.0) -> None:
        if not url:
            raise ValueError("url is required")
        if not key:
            raise ValueError("key is required")
        self.url = url.rstrip("/") + "/rpc"
        self.key = key
        self.timeout = timeout

    def call(self, service: str, method: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        body = json.dumps(
            {"requestId": str(uuid.uuid4()), "service": service, "method": method, "payload": payload or {}}
        ).encode("utf-8")

        req = urllib.request.Request(
            self.url,
            data=body,
            method="POST",
            headers={"content-type": "application/json", "x-zedgi-key": self.key},
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                parsed = json.loads(resp.read().decode("utf-8"))
                status = resp.status
        except urllib.error.HTTPError as exc:  # 4xx/5xx still carry a JSON body
            try:
                parsed = json.loads(exc.read().decode("utf-8"))
            except Exception:
                raise RpcError(f"Zedgi request failed ({exc.code})", status=exc.code) from exc
            status = exc.code
        except urllib.error.URLError as exc:
            raise RpcError(f"Zedgi connection failed: {exc.reason}", code="ZEDGI_CONNECTION") from exc

        if not parsed.get("ok"):
            err = parsed.get("error") or {}
            raise RpcError(
                err.get("message", f"Zedgi call failed ({status})"),
                code=err.get("code", "ZEDGI_ERROR"),
                status=status,
                details=err.get("details"),
            )

        return parsed.get("result")
