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
from typing import Any, Dict, Optional, Tuple, Union

from .crypto import encrypt_credential, hmac_sign, random_nonce, sha256_hex

Credential = Dict[str, Any]
CredentialSelector = Union[str, Credential]
CredentialProfiles = Dict[str, Dict[str, Credential]]
_CRED_BLOB_TTL_SECONDS = 55 * 60


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
      - ``signing_secret``: optional HMAC secret. Auto-pulled and cached when
        omitted, so every request is signed without you supplying it.
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
        credential: Optional[Credential] = None,
        credentials: Optional[CredentialProfiles] = None,
        public_key: Optional[str] = None,
        account_id: Optional[str] = None,
        key_version: Optional[int] = None,
        cache: bool = True,
        test_node_uuid: Optional[str] = None,
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
        self.credentials = credentials or {}
        self.public_key = public_key
        self.account_id = account_id
        self.key_version = key_version
        self._pinned_account_key = public_key is not None and account_id is not None and key_version is not None
        self.cache = cache
        self.test_node_uuid = test_node_uuid
        self._cred_blobs: Dict[str, Tuple[float, str]] = {}
        self._signing_secret: Optional[str] = signing_secret
        self._bootstrap_resolved = False
        # Encrypted full node target from bootstrap (required for /rpc as x-zedgi-node).
        self.node: Optional[str] = None

    # -- account key resolution -------------------------------------------------

    def resolve_credential(self, service: str, selector: Optional[CredentialSelector] = None) -> Optional[Credential]:
        if isinstance(selector, dict):
            return selector
        if isinstance(selector, str):
            credential = self.credentials.get(service, {}).get(selector)
            if credential is None:
                raise ValueError(f'Zedgi credential profile "{selector}" was not found for {service}')
            return credential
        return self.credentials.get(service, {}).get("default") or self.credential

    def _credential_parts(self, credential: Optional[Credential]) -> Dict[str, Any]:
        if not credential:
            return {"encrypted": None, "header": None}
        encrypted = dict(credential)
        header = encrypted.pop("header", None)
        if header is not None and not isinstance(header, dict):
            raise ValueError("credential.header must be a dict")
        return {"encrypted": encrypted, "header": header}

    def _resolve_bootstrap(self) -> None:
        if self._bootstrap_resolved:
            return

        has_explicit_key = self.public_key and self.account_id and self.key_version is not None
        explicit_secret = self._signing_secret

        # Always bootstrap for the node blob (required on /rpc). Explicit key/secret
        # can still override key material after the response.
        req = urllib.request.Request(
            self.base + "/api/account/bootstrap",
            method="GET",
            headers={"x-zedgi-key": self.key},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                parsed = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise RpcError(f"Failed to bootstrap client config: {exc}", code="ZEDGI_BOOTSTRAP_FAIL") from exc

        if not parsed.get("ok") or not parsed.get("result"):
            raise RpcError("Failed to bootstrap client config", code="ZEDGI_BOOTSTRAP_FAIL")

        result = parsed["result"]
        if not has_explicit_key:
            self.public_key = result["key"]["public_key"]
            self.account_id = result["key"]["id"]
            self.key_version = result["key"]["key_version"]
        if not explicit_secret:
            self._signing_secret = result["signing_secret"]

        self.node = result.get("node") or result.get("node_prefix")
        if not self.node and not self.test_node_uuid:
            raise RpcError("Bootstrap returned no node", code="ZEDGI_NO_NODE")
        self._bootstrap_resolved = True

    def _resolve_account_key(self) -> Dict[str, Any]:
        self._resolve_bootstrap()
        return {"public_key": self.public_key, "id": self.account_id, "key_version": self.key_version}

    def _resolve_signing_secret(self) -> str:
        # Auto-pull the HMAC signing secret (and cache it) when not supplied, so
        # the developer never has to handle it. Authed by x-zedgi-key.
        self._resolve_bootstrap()
        return self._signing_secret  # type: ignore

    def _resolve_cred_blob(self, credential: Optional[Credential]) -> Optional[str]:
        if not credential:
            return None
        ak = self._resolve_account_key()
        encrypted = self._credential_parts(credential)["encrypted"]
        cache_key = f'{ak["id"]}:{ak["key_version"]}:{ak["public_key"]}:{json.dumps(encrypted, sort_keys=True, separators=(",", ":"))}'
        now = time.time()
        cached = self._cred_blobs.get(cache_key)
        if self.cache and cached and cached[0] > now:
            return cached[1]
        blob = encrypt_credential(encrypted, ak["public_key"], ak["id"], ak["key_version"])
        if self.cache:
            self._cred_blobs[cache_key] = (now + _CRED_BLOB_TTL_SECONDS, blob)
            if len(self._cred_blobs) > 256:
                self._cred_blobs.pop(next(iter(self._cred_blobs)), None)
        return blob

    # -- request ----------------------------------------------------------------

    def _auto_key_mode(self) -> bool:
        # True when we auto-pull the account key (so we can re-pull on rotation).
        return not self._pinned_account_key

    def _send_once(
        self,
        service: str,
        method: str,
        payload: Optional[Dict[str, Any]],
        credential: Optional[Credential],
    ) -> tuple:
        credential_header = self._credential_parts(credential)["header"]
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

        # Every request is signed; the signing secret is auto-pulled when not supplied.
        secret = self._resolve_signing_secret()
        if not self.test_node_uuid:
            if not self.node:
                raise RpcError("Missing node from bootstrap", code="ZEDGI_NO_NODE")
            headers["x-zedgi-node"] = self.node

        ts = str(int(time.time() * 1000))
        nonce = random_nonce()
        headers["x-zedgi-ts"] = ts
        headers["x-zedgi-nonce"] = nonce
        headers["x-zedgi-sig"] = hmac_sign(f"{ts}:{nonce}:{sha256_hex(body_str)}", secret)

        cred_blob = self._resolve_cred_blob(credential)
        if cred_blob:
            headers["x-zedgi-cred"] = cred_blob
        if self.test_node_uuid:
            headers["x-zedgi-node-uuid"] = self.test_node_uuid

        req = urllib.request.Request(self.url, data=body, method="POST", headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_node = resp.getheader("x-zedgi-node")
                if resp_node and self.node != resp_node:
                    self.node = resp_node
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # 4xx/5xx still carry a JSON body
            try:
                return exc.code, json.loads(exc.read().decode("utf-8"))
            except Exception:
                raise RpcError(f"Zedgi request failed ({exc.code})", status=exc.code) from exc
        except urllib.error.URLError as exc:
            raise RpcError(f"Zedgi connection failed: {exc.reason}", code="ZEDGI_CONNECTION") from exc

    def call(
        self,
        service: str,
        method: str,
        payload: Optional[Dict[str, Any]] = None,
        credential: Optional[CredentialSelector] = None,
    ) -> Any:
        resolved_credential = self.resolve_credential(service, credential)
        # Two attempts at most: on a rotated/outdated key (in auto mode) we drop the
        # cached public key + ciphertext, re-pull the current key, and retry once.
        for attempt in range(2):
            status, parsed = self._send_once(service, method, payload, resolved_credential)
            if parsed.get("ok"):
                return parsed.get("result")

            err = parsed.get("error") or {}
            stale_key = status == 412 or err.get("code") == "CRED_DECRYPT_FAILED"
            if attempt == 0 and self._auto_key_mode() and stale_key:
                self._bootstrap_resolved = False
                self.public_key = None  # force a re-pull of the current active key
                self.account_id = None
                self.key_version = None
                if resolved_credential is not None:
                    self._cred_blobs.clear()
                continue

            raise RpcError(
                err.get("message", f"Zedgi call failed ({status})"),
                code=err.get("code", "ZEDGI_ERROR"),
                status=status,
                details=err.get("details"),
            )
        raise RpcError("Zedgi call failed")  # unreachable
