"""Zedgi — call your own Redis, Postgres, and MySQL from any Python runtime.

    from zedgi import create_client

    zedgi = create_client(url="https://dev123.zedgi.app", key=os.environ["ZEDGI_KEY"])
    redis = zedgi.redis()
    redis.set("foo", "bar")
    print(redis.get("foo"))
"""
from __future__ import annotations

from ._version import __version__
from .client import RpcError, Transport
from .mysql import MySQLClient
from .postgres import PostgresClient
from .redis import RedisClient


class ZedgiClient:
    def __init__(self, url: str, key: str, timeout: float = 10.0) -> None:
        self._transport = Transport(url=url, key=key, timeout=timeout)

    def redis(self) -> RedisClient:
        return RedisClient(self._transport)

    def postgres(self) -> PostgresClient:
        return PostgresClient(self._transport)

    def mysql(self) -> MySQLClient:
        return MySQLClient(self._transport)


def create_client(url: str, key: str, timeout: float = 10.0) -> ZedgiClient:
    """Create a Zedgi client.

    :param url:     Your personal Zedgi endpoint, e.g. ``https://dev123.zedgi.app``
    :param key:     A Zedgi API key (``zk_...``)
    :param timeout: Per-request timeout in seconds (default 10)
    """
    return ZedgiClient(url=url, key=key, timeout=timeout)


__all__ = [
    "create_client",
    "ZedgiClient",
    "RedisClient",
    "PostgresClient",
    "MySQLClient",
    "RpcError",
    "__version__",
]
