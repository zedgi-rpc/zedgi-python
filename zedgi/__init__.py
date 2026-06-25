"""Zedgi — call your own Redis, Postgres, and MySQL from any Python runtime.

    from zedgi import create_client

    zedgi = create_client(url="https://dev123.zedgi.app", key=os.environ["ZEDGI_KEY"])
    redis = zedgi.redis()
    redis.set("foo", "bar")
    print(redis.get("foo"))
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from ._version import __version__
from .client import RpcError, Transport
from .mysql import MySQLClient
from .postgres import PostgresClient
from .queue import Queue
from .redis import RedisClient


class ZedgiClient:
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
        self._transport = Transport(
            url=url,
            key=key,
            timeout=timeout,
            signing_secret=signing_secret,
            credential=credential,
            public_key=public_key,
            account_id=account_id,
            key_version=key_version,
            cache=cache,
        )

    def redis(self) -> RedisClient:
        return RedisClient(self._transport)

    def postgres(self) -> PostgresClient:
        return PostgresClient(self._transport)

    def mysql(self) -> MySQLClient:
        return MySQLClient(self._transport)

    def queue(self, name: str) -> Queue:
        return Queue(self._transport, name)


def create_client(
    url: str,
    key: str,
    timeout: float = 10.0,
    signing_secret: Optional[str] = None,
    credential: Optional[Dict[str, Any]] = None,
    public_key: Optional[str] = None,
    account_id: Optional[str] = None,
    key_version: Optional[int] = None,
    cache: bool = True,
) -> ZedgiClient:
    """Create a Zedgi client.

    :param url:            Your personal Zedgi endpoint, e.g. ``https://dev123.zedgi.app``
    :param key:            A Zedgi API key (``zk_...`` public identifier)
    :param timeout:        Per-request timeout in seconds (default 10)
    :param signing_secret: optional HMAC signing secret; auto-pulled + cached when omitted
    :param credential:     DB/service credentials encrypted client-side (zero-knowledge)
    :param public_key:     Account X25519 public key (base64url); auto-pulled if omitted
    :param account_id:     32-hex account id for the cred blob; auto-pulled if omitted
    :param key_version:    Keypair rotation counter; auto-pulled if omitted
    :param cache:          Cache the encrypted credential blob in memory (default True)
    """
    return ZedgiClient(
        url=url,
        key=key,
        timeout=timeout,
        signing_secret=signing_secret,
        credential=credential,
        public_key=public_key,
        account_id=account_id,
        key_version=key_version,
        cache=cache,
    )


__all__ = [
    "create_client",
    "ZedgiClient",
    "RedisClient",
    "PostgresClient",
    "MySQLClient",
    "Queue",
    "RpcError",
    "__version__",
]
