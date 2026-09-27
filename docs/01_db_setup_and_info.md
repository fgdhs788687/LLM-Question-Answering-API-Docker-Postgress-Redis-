# Async Database Setup in FastAPI — Complete Reference

A reusable guide for setting up SQLAlchemy with FastAPI, both async and sync.
Applies to any Postgres + FastAPI project.

---

## 1. The Mental Model (Three Layers)

Think of a database connection like a **library**:

| Layer | What it is | How many |
|---|---|---|
| **Engine** | The library building + staff. Manages a pool of connections. | **One per app** |
| **Session** | Your visit to the library. You borrow, read, return. | **One per request** |
| **Base / Model** | The book catalog rules. | Defined once |

**Most common beginner mistake:** creating the engine or session in the wrong place.
Engine = app-lifetime. Session = request-lifetime. Never mix them up.

---

## 2. Why Async Matters

FastAPI endpoints are `async def`. If DB calls are sync, the event loop is
**blocked** during every query — no other request can be served.

**Rule:** async endpoint → async DB driver → async session. Match them.

---

## 3. File Layout

```
app/database/
├── __init__.py
├── base.py       # the declarative Base for models
├── session.py    # engine + session factory
└── deps.py       # the FastAPI get_db() dependency
```

Can be merged into one `db.py`, but splitting teaches separation clearly.

---

## 4. Install Drivers

```bash
# Async (what you'll use 95% of the time)
uv add sqlalchemy asyncpg

# Sync (only for Celery workers / scripts)
uv add psycopg2-binary
```

- `sqlalchemy` — the ORM
- `asyncpg` — async Postgres driver (enables `postgresql+asyncpg://`)
- `psycopg2-binary` — sync Postgres driver (enables `postgresql://` or `postgresql+psycopg2://`)

---

## 5. Async Setup

### 5.1 Engine + Session Factory

```python
# app/database/session.py
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.settings import get_settings

settings = get_settings()

engine = create_async_engine(
    str(settings.database_url),     # PostgresDsn → needs str()
    echo=False,                      # True = log every SQL (debugging)
    pool_size=5,                     # connections kept open
    max_overflow=10,                 # extra connections under load
    pool_pre_ping=True,              # health check before use
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,          # CRITICAL for async
    autoflush=False,
)
```

#### Why each parameter

- **`pool_size=5`** — always keep 5 connections ready. Reuse > reopening.
- **`max_overflow=10`** — burst allowance. Total max = 15.
- **`pool_pre_ping=True`** — auto-reconnect if DB restarted. Cheap insurance.
- **`expire_on_commit=False`** — after `commit()`, SQLAlchemy normally expires
  objects, forcing a DB re-fetch on next attribute access. In async that requires
  an `await` and breaks plain attribute access. **#1 async gotcha.**
- **`autoflush=False`** — prevents accidental flushes mid-query.

### 5.2 Base Class (for models)

```python
# app/database/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

Every model (`User`, `ChatLog`, etc.) inherits from `Base`. Alembic reads
`Base.metadata` to autogenerate migrations.

### 5.3 FastAPI Dependency

```python
# app/database/deps.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

#### Why `yield`?

FastAPI's dependency injection has a **lifespan**:
1. Request arrives
2. `get_db()` opens a session
3. Endpoint runs with `db=Depends(get_db)`
4. Endpoint finishes (or raises)
5. Back in `get_db()`: rollback on error, then close

Guarantees cleanup — no leaks, no "pool exhausted" surprises.

#### Why `try/except/finally`?

`async with` already closes on exit. The explicit `except` adds **rollback on
error** — prevents a dirty connection from going back into the pool.

### 5.4 Use in an Endpoint

```python
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.deps import get_db

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "up"}
```

Everything DB-related in async needs `await`.

---

## 6. Sync Setup (For Reference)

```python
# sync version — do NOT use with async endpoints
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

engine = create_engine(str(settings.database_url), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 7. Async vs Sync — Comparison

| Async (default) | Sync (workers/scripts) |
|---|---|
| `create_async_engine` | `create_engine` |
| `async_sessionmaker` | `sessionmaker` |
| `AsyncSession` | `Session` |
| `await db.execute(...)` | `db.execute(...)` |
| `async with`, `await session.close()` | `with`, `session.close()` |
| Driver: `asyncpg` | Driver: `psycopg2` |
| URL: `postgresql+asyncpg://...` | URL: `postgresql://...` |

**Rule of thumb:** async endpoint → async DB. Celery/script → sync is fine.
**Never mix** (sync `Session` with async engine = crash).

---

## 8. Gotchas to Memorize

1. **One engine per app.** Not per request. Define once at module level.
2. **One session per request.** FastAPI's `Depends(get_db)` handles this.
3. **`expire_on_commit=False`** — always, for async.
4. **Sessions are not thread-safe.** Don't share across threads.
5. **`await session.commit()`** — don't forget the `await`.
6. **`str(settings.database_url)`** — `PostgresDsn` isn't a plain str.
7. **URL must match driver.** `postgresql+asyncpg://` for async.
   Mismatch = confusing driver errors.

---

## 9. Environment Variables

```env
# Async (correct for this project)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname

# Sync (if needed for workers)
DATABASE_URL_SYNC=postgresql+psycopg2://user:pass@localhost:5432/dbname
```

**Note the `+asyncpg`.** Without it, SQLAlchemy tries the sync driver and
fails on your async engine.

---

## 10. Quick Setup Checklist

- [ ] `uv add sqlalchemy asyncpg`
- [ ] `.env` uses `postgresql+asyncpg://`
- [ ] `app/database/base.py` — `Base(DeclarativeBase)`
- [ ] `app/database/session.py` — engine + `AsyncSessionLocal`
- [ ] `app/database/deps.py` — `get_db()` dependency
- [ ] Endpoint uses `db: AsyncSession = Depends(get_db)`
- [ ] Test with `await db.execute(text("SELECT 1"))`

---

## 11. Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| `InvalidRequestError: no driver` | URL lacks `+asyncpg` | Use `postgresql+asyncpg://` |
| `MissingGreenlet` | Sync call inside async context | Add `await`; use async driver |
| `coroutine was never awaited` | Forgot `await` on `commit()`/`execute()` | Add `await` |
| `Connection pool exhausted` | Sessions not closed | Verify `get_db()` teardown |
| `DetachedInstanceError` | Object accessed after session closed | Use `expire_on_commit=False` and load relations eagerly |
| `InvalidPasswordError` from asyncpg | Bad credentials in URL | URL-encode special chars in password |

---

*Save this file as `docs/database-setup.md` in your repo.*