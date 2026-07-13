"""Zedgi — call your own Redis, Postgres, and MySQL from any Python runtime.

    from zedgi import create_client

    zedgi = create_client(url="https://dev123.zedgi.app", key=os.environ["ZEDGI_KEY"])
    redis = zedgi.redis()
    redis.set("foo", "bar")
    print(redis.get("foo"))
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Union

from ._version import __version__
from .client import RpcError, Transport
from .mysql import MySQLClient
from .memcached import MemcachedClient
from .postgres import PostgresClient
from .queue import Queue
from .redis import RedisClient

Credential = Dict[str, Any]
CredentialSelector = Union[str, Credential]
CredentialProfiles = Dict[str, Dict[str, Credential]]


class ZedgiClient:
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
        self._transport = Transport(
            url=url,
            key=key,
            timeout=timeout,
            signing_secret=signing_secret,
            credential=credential,
            credentials=credentials,
            public_key=public_key,
            account_id=account_id,
            key_version=key_version,
            cache=cache,
            test_node_uuid=test_node_uuid,
        )

    def redis(self, credential: Optional[CredentialSelector] = None) -> RedisClient:
        return RedisClient(self._transport, credential)

    def postgres(self, credential: Optional[CredentialSelector] = None) -> PostgresClient:
        return PostgresClient(self._transport, credential)

    def mysql(self, credential: Optional[CredentialSelector] = None) -> MySQLClient:
        return MySQLClient(self._transport, credential)

    def memcached(self, credential: Optional[CredentialSelector] = None) -> MemcachedClient:
        return MemcachedClient(self._transport, credential)

    def queue(self, name: str, credential: Optional[CredentialSelector] = None) -> Queue:
        return Queue(self._transport, name, credential)


def create_client(
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
) -> ZedgiClient:
    """Create a Zedgi client.

    :param url:            Your personal Zedgi endpoint, e.g. ``https://dev123.zedgi.app``
    :param key:            A Zedgi API key (``zk_...`` public identifier)
    :param timeout:        Per-request timeout in seconds (default 10)
    :param signing_secret: optional HMAC signing secret; auto-pulled + cached when omitted
    :param credential:     legacy default DB/service credential encrypted client-side
    :param credentials:    named credentials per service; use "default" for the service default
    :param public_key:     Account X25519 public key (base64url); auto-pulled if omitted
    :param account_id:     32-hex account id for the cred blob; auto-pulled if omitted
    :param key_version:    Keypair rotation counter; auto-pulled if omitted
    :param cache:          Cache the encrypted credential blob in memory (default True)
    :param test_node_uuid: Admin diagnostics only; force /rpc through one proxy node
    """
    return ZedgiClient(
        url=url,
        key=key,
        timeout=timeout,
        signing_secret=signing_secret,
        credential=credential,
        credentials=credentials,
        public_key=public_key,
        account_id=account_id,
        key_version=key_version,
        cache=cache,
        test_node_uuid=test_node_uuid,
    )


__all__ = [
    "create_client",
    "ZedgiClient",
    "RedisClient",
    "PostgresClient",
    "MySQLClient",
    "MemcachedClient",
    "Queue",
    "RpcError",
    "__version__",
]
