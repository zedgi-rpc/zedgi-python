"""Low-level HTTP client for the Zedgi RPC endpoint.

Uses only the Python standard library (``urllib``) for transport. Credential
encryption (the zero-knowledge model) additionally requires the ``cryptography``
package — install the ``zedgi[crypto]`` extra. Request signing and the SHA-256
body hash use the stdlib only.
"""
from __future__ import annotations

import json
import time
import uuid
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .crypto import encrypt_credential, hmac_sign, random_nonce, sha256_hex


class RpcError(Exception):
    """Raised when the Zedgi API returns an error envelope."""

    def __init__(self, message: str, code: str = "ZEDGI_ERROR", status: int = 0, details: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details


class Transport:
    """Holds connection options and performs the raw ``POST /rpc`` call.

    Zero-knowledge parameters (all optional):
      - ``signing_secret``: HMAC secret; when set, every request is signed.
      - ``credential``: dict of DB/service credentials encrypted client-side.
      - ``public_key`` / ``account_id`` / ``key_version``: account key material;
        auto-pulled from ``/api/account/keys/current`` when omitted.
      - ``cache``: cache the encrypted credential blob in memory (default True).
    """

    def __init__(
        self,
        url: str,
        key: str,
        timeout: float = 10.0,
        signing_secret: Optional[str] = None,
        credential: Optional[Dict[str, Any]] = None,
        public_key: Optional[str] = None,
        account_id: Optional[str] = None,
        key_version: Optional[int] = None,
        cache: bool = True,
    ) -> None:
        if not url:
            raise ValueError("url is required")
        if not key:
            raise ValueError("key is required")
        self.base = url.rstrip("/")
        self.url = self.base + "/rpc"
        self.key = key
        self.timeout = timeout
        self.signing_secret = signing_secret
        self.credential = credential
        self.public_key = public_key
        self.account_id = account_id
        self.key_version = key_version
        self.cache = cache
        self._cred_blob: Optional[str] = None

    # -- account key resolution -------------------------------------------------

    def _credential_parts(self) -> Dict[str, Any]:
        if not self.credential:
            return {"encrypted": None, "header": None}
        encrypted = dict(self.credential)
        header = encrypted.pop("header", None)
        if header is not None and not isinstance(header, dict):
            raise ValueError("credential.header must be a dict")
        return {"encrypted": encrypted, "header": header}

    def _resolve_account_key(self) -> Dict[str, Any]:
        if self.public_key and self.account_id and self.key_version is not None:
            return {"public_key": self.public_key, "id": self.account_id, "key_version": self.key_version}

        req = urllib.request.Request(
            self.base + "/api/account/keys/current",
            method="GET",
            headers={"x-zedgi-key": self.key},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            parsed = json.loads(resp.read().decode("utf-8"))
        if not parsed.get("ok") or not parsed.get("result"):
            raise RpcError("Failed to fetch account public key", code="ZEDGI_KEY_PULL")
        result = parsed["result"]
        self.public_key = result["public_key"]
        self.account_id = result["id"]
        self.key_version = result["key_version"]
        return result

    def _resolve_cred_blob(self) -> Optional[str]:
        if not self.credential:
            return None
        if self.cache and self._cred_blob is not None:
            return self._cred_blob
        ak = self._resolve_account_key()
        blob = encrypt_credential(self._credential_parts()["encrypted"], ak["public_key"], ak["id"], ak["key_version"])
        if self.cache:
            self._cred_blob = blob
        return blob

    # -- request ----------------------------------------------------------------

    def call(self, service: str, method: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        credential_header = self._credential_parts()["header"]
        body_payload: Dict[str, Any] = {
            "requestId": str(uuid.uuid4()),
            "service": service,
            "method": method,
            "payload": payload or {},
        }
        if credential_header is not None:
            body_payload["credentialHeader"] = credential_header
        body_str = json.dumps(body_payload)
        body = body_str.encode("utf-8")

        headers = {"content-type": "application/json", "x-zedgi-key": self.key}

        if self.signing_secret:
            ts = str(int(time.time() * 1000))
            nonce = random_nonce()
            headers["x-zedgi-ts"] = ts
            headers["x-zedgi-nonce"] = nonce
            headers["x-zedgi-sig"] = hmac_sign(f"{ts}:{nonce}:{sha256_hex(body_str)}", self.signing_secret)

        cred_blob = self._resolve_cred_blob()
        if cred_blob:
            headers["x-zedgi-cred"] = cred_blob

        req = urllib.request.Request(self.url, data=body, method="POST", headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                parsed = json.loads(resp.read().decode("utf-8"))
                status = resp.status
        except urllib.error.HTTPError as exc:  # 4xx/5xx still carry a JSON body
            # Key rotated: drop cached blob so the next call re-pulls + re-encrypts.
            if exc.code == 412:
                self._cred_blob = None
                if not (self.public_key and self.account_id and self.key_version is not None):
                    self.public_key = None
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
