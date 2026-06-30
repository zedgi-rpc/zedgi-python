# zedgi (Python)

Call your own **Redis, Postgres, and MySQL** from any Python runtime over HTTPS — no TCP sockets required. Built on the standard library only (zero dependencies).

```bash
pip install zedgi
```

## Quick Start

```python
import os
from zedgi import create_client

zedgi = create_client(
    url="https://dev123.zedgi.app",
    key=os.environ["ZEDGI_KEY"],
    credentials={
        "redis": {"default": {"password": os.environ["REDIS_PASSWORD"], "db": 0}},
        "postgres": {"default": {"user": "app", "password": os.environ["PG_PASSWORD"], "database": "app"}},
        "mysql": {"default": {"user": "app", "password": os.environ["MYSQL_PASSWORD"], "database": "app"}},
    },
)

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

You normally pass **`url`, `key`, and either `credential` or `credentials`** —
request signing is automatic (the signing secret is auto-pulled and cached; you
don't supply it).

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
- **`credential` / `credentials`** — your **own database** credentials. `host`/`port` come from the registered service, not here. Shapes:
  - redis: `{"password": "s3cr3t", "db": 2, "header": {"x-firewall-token": "..."}}`; all three keys are optional, and you can omit the credential entirely if Redis is password-less
  - postgres: `{"user": "app", "password": "s3cr3t", "database": "prod", "ssl": True, "header": {"x-firewall-token": "..."}}`; `ssl` and `header` are optional
  - mysql: `{"user": "app", "password": "s3cr3t", "database": "prod", "ssl": True, "header": {"x-firewall-token": "..."}}`; `ssl` and `header` are optional
- **`signing_secret`** — **optional.** Auto-pulled via `GET /api/account/signing-secret` (authed by `key`) and cached. Pass it only to manage signing yourself.

`credential["header"]` is optional. When present, it is excluded from ECIES encryption and sent as signed plaintext metadata for proxy/firewall integrations.

### Credential profiles and headers

Use `credentials` when one app talks to more than one service, Redis logical DB,
database user, or firewall/header variant:

```python
client = create_client(
    url="https://YOUR_SUBDOMAIN.zedgi.app",
    key=os.environ["ZEDGI_KEY"],
    credentials={
        "redis": {
            "default": {"password": os.environ["REDIS_PASSWORD"], "db": 0},
            "cache": {
                "password": os.environ["REDIS_PASSWORD"],
                "db": 1,
                "header": {"x-firewall-token": os.environ["REDIS_FIREWALL_TOKEN"]},
            },
        },
        "postgres": {
            "default": {"user": "app", "password": os.environ["PG_PASSWORD"], "database": "app"},
            "reporting": {
                "user": "reporter",
                "password": os.environ["PG_REPORTING_PASSWORD"],
                "database": "reports",
            },
        },
    },
)

redis = client.redis()              # credentials["redis"]["default"]
cache = client.redis("cache")       # credentials["redis"]["cache"]
pg = client.postgres("reporting")
temp = client.redis({"password": os.environ["REDIS_PASSWORD"], "db": 2})
```

Credential selection order is: ad-hoc dict, named profile, service `default`,
legacy `credential`, then no credential. If you request a missing profile, the
client raises before making the HTTP request.

`header` is optional and special: it is removed from the encrypted credential, added to the
signed RPC body as `credentialHeader`, and forwarded as plaintext metadata for
proxy/firewall integrations. Put only values there that the receiving proxy or
firewall must see.

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

## BullMQ queues

BullMQ rides on your existing **Redis** service — there's no separate service to register.
Each op is sent as the redis service's `bull:<method>` and runs the real BullMQ operation
(default `bull` key prefix, so jobs interoperate with your own workers).

```python
queue = zedgi.queue("emails")          # uses credentials["redis"]["default"]
cache_queue = zedgi.queue("emails", "cache")  # uses credentials["redis"]["cache"]

# Produce
queue.add("send", {"to": "dev@example.com"}, {"attempts": 3})

# Inspect
queue.get_job_counts()      # {"waiting": 1, "active": 0, ...}
queue.get_job("42")
queue.get_snapshot()        # counts across all queues — for dashboards

# Manage
queue.pause()
queue.retry_job("42")
queue.clean(0, 1000, "completed")
```

Workers/consumers still run in your own runtime against the same Redis — this covers producing
jobs and inspecting/managing queue state, not running the processors.

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
- `RedisClient`, `PostgresClient`, `MySQLClient`, `Queue`
- `RpcError`

All clients are thin (stdlib only) for the RPC facade. For the full zero-knowledge "link" (client-side ECIES encryption of your DB credentials into `x-zedgi-cred` + request signing), supply `key` + `credential` or `credentials`. The client auto-pulls both the signing secret (`GET /api/account/signing-secret`) and the account public key (`GET /api/account/keys/current`) using your `key`, and caches them — so you don't manage either. If a credential/profile contains `header`, it is signed and forwarded separately instead of being public-key encrypted. See https://zedgi.app/docs for the full option reference.

## Related

- JavaScript/TypeScript client: [`@zedgi/zedgi-client`](https://www.npmjs.com/package/@zedgi/zedgi-client)
- Full documentation & API reference: https://zedgi.app/docs (includes credential linking, key rotation, and public key auto-fetch)
- Dashboard: https://zedgi.app

## License

MIT licensed. Part of the [ZedGi](https://zedgi.app) platform.
