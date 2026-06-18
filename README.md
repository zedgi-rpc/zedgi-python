# zedgi (Python)

Call your own **Redis, Postgres, and MySQL** from any Python runtime over HTTPS — no TCP sockets required. Built on the standard library only (zero dependencies).

```bash
pip install zedgi
```

## Quick Start

```python
import os
from zedgi import create_client

zedgi = create_client(url="https://dev123.zedgi.app", key=os.environ["ZEDGI_KEY"])

# Redis
redis = zedgi.redis()
redis.set("hello", "world")
print(redis.get("hello"))            # 'world'
redis.call("HSET", "user:1", "name", "Ada")

# Postgres
pg = zedgi.postgres()
result = pg.query("SELECT NOW() AS ts")
print(result["rows"])

# MySQL
mysql = zedgi.mysql()
print(mysql.query("SELECT 1 AS n")["rows"])
```

## Installation

```bash
pip install zedgi
```

Requires Python 3.8+.

## Creating a Client

```python
from zedgi import create_client, ZedgiClient

client: ZedgiClient = create_client(
    url="https://YOUR_SUBDOMAIN.zedgi.app",
    key="zk_...",           # your API key
    timeout=10.0,          # seconds (default)
)
```

You normally pass just **`url`, `key`, and `credential`** — request signing is
automatic (the signing secret is auto-pulled and cached; you don't supply it).

```python
client = create_client(
    url="https://YOUR_SUBDOMAIN.zedgi.app",
    key="zk_...",                       # from the dashboard; signing is automatic
    credential={                        # your DB secrets — host/port are on the service
        "user": "app",
        "password": os.environ["DB_PASSWORD"],
        "database": "main",
        "header": {
            "x-firewall-token": os.environ["DB_FIREWALL_TOKEN"],
        },
    },
)
```

**Where each value comes from**

- **`key`** — created in the dashboard (open your service → **+ New key**), sent as `x-zedgi-key`.
- **`credential`** — your **own database** credentials. `host`/`port` come from the registered service, not here. Shapes:
  - redis: `{"password": "s3cr3t"}` (or add `"db": 2`; omit entirely if password-less)
  - postgres: `{"user": "app", "password": "s3cr3t", "database": "prod", "ssl": True}`
  - mysql: `{"user": "app", "password": "s3cr3t", "database": "prod"}`
- **`signing_secret`** — **optional.** Auto-pulled via `GET /api/account/signing-secret` (authed by `key`) and cached. Pass it only to manage signing yourself.

`credential["header"]` is excluded from ECIES encryption and sent as signed plaintext metadata for proxy/firewall integrations.

## Redis

The Redis client exposes many common commands and a generic `call()` escape hatch. Unknown method names are forwarded as custom hooks.

```python
redis = zedgi.redis()

redis.ping()                          # 'PONG'
redis.set("key", "value", "EX", 60)
redis.get("key")
redis.delete("key1", "key2")
redis.hset("user:1", "name", "Ada")
redis.lrange("queue", 0, -1)
redis.zadd("scores", 100, "player1")

# Generic command
redis.call("ZREVRANGE", "leaderboard", 0, 9, "WITHSCORES")

# Pipeline / MULTI
redis.pipeline([("SET", ["a", "1"]), ("INCR", ["a"])])
redis.multi([...])
```

## Postgres & MySQL

```python
pg = zedgi.postgres()
mysql = zedgi.mysql()

# Query
result = pg.query("SELECT * FROM users WHERE id = $1", [42])
# {"rows": [...], "rowCount": 1, "fields": [...] }

# Transaction
pg.transaction([
    {"sql": "UPDATE accounts SET balance = balance - $1 WHERE id = $2", "params": [100, 1]},
    {"sql": "UPDATE accounts SET balance = balance + $1 WHERE id = $2", "params": [100, 2]},
])
```

MySQL returns a slightly different shape: `{"rows": [...], "fields": [...]}` (fields are plain strings).

## Custom Hooks (paid feature)

Register hooks in your ZedGi dashboard, then invoke them by name.

```python
# Redis Lua hook (KEYS + ARGV)
redis.hook("topUsers", keys=["leaderboard"], args=[10])

# SQL hook
pg.hook("activeUsers", params=[30])

# Magic proxy — call unregistered names directly
redis.topUsers("leaderboard", 10)
pg.activeUsers(30)
```

See the [Custom Hooks documentation](https://zedgi.app/docs/guide/custom-hooks) for registration details.

## Error Handling

All RPC errors raise `zedgi.RpcError`:

```python
from zedgi import RpcError

try:
    redis.hook("notRegistered")
except RpcError as e:
    print(e.code)     # e.g. "ZEDGI_HOOK_NOT_FOUND"
    print(e.status)   # HTTP status
    print(e.details)
    print(str(e))
```

## Low-level Transport

If you need full control you can use the transport directly:

```python
from zedgi.client import Transport

t = Transport(url="https://...", key="zk_...", timeout=10)
result = t.call("redis", "get", {"args": ["mykey"]})
```

## Package Contents

- `create_client`
- `ZedgiClient`
- `RedisClient`, `PostgresClient`, `MySQLClient`
- `RpcError`

All clients are thin (stdlib only) for the RPC facade. For the full zero-knowledge "link" (client-side ECIES encryption of your DB credentials into `x-zedgi-cred` + request signing), supply just `key` + `credential`. The client auto-pulls both the signing secret (`GET /api/account/signing-secret`) and the account public key (`GET /api/account/keys/current`) using your `key`, and caches them — so you don't manage either. If `credential["header"]` is present, it is signed and forwarded separately instead of being public-key encrypted. See https://zedgi.app/docs for the full option reference.

## Related

- JavaScript/TypeScript client: [`@zedgi/zedgi-client`](https://www.npmjs.com/package/@zedgi/zedgi-client)
- Full documentation & API reference: https://zedgi.app/docs (includes credential linking, key rotation, and public key auto-fetch)
- Dashboard: https://zedgi.app

## License

MIT licensed. Part of the [ZedGi](https://zedgi.app) platform.
