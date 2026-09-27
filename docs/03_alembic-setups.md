# Alembic Setup in FastAPI — Complete Reference

How to set up, run, and maintain database migrations in a FastAPI project
with an async PostgreSQL driver. Includes the async-specific gotchas most
tutorials skip.

---

## 1. The Mental Model

Think of your database like a **building**:

| Thing | Role |
|---|---|
| **Your models** | The blueprint (what the building *should* look like) |
| **The actual database** | The building as it stands today |
| **Alembic** | The construction crew applying changes to match the blueprint |
| **`alembic_version` table** | The ledger saying "we're currently at revision X" |

Alembic tracks every schema change as a **migration file**. Each file is
a numbered page in a history book. To move forward, run the next page.
To go back, tear out the last one.

**Why it matters:** you never manually run `CREATE TABLE`. You change a
model, generate a migration, run it, and the DB updates. Same flow in dev,
staging, production. This is what "production-ready" means in practice.

---

## 2. The Three Core Concepts

| Concept | What it is |
|---|---|
| **`alembic.ini`** | Config file. Points at your migrations folder and log settings. |
| **`env.py`** | The "how to connect" script. You edit this once, then rarely. |
| **`versions/`** | One `.py` file per change. Auto-generated, then applied. |

And two commands that do 90% of the work:

```bash
alembic revision --autogenerate -m "message"   # write a new migration
alembic upgrade head                            # apply all pending migrations
```

---

## 3. The Workflow (Memorize This)

```
You edit a model                  (e.g. add a column to User)
        ↓
alembic revision --autogenerate
        ↓
Alembic compares models ↔ DB, writes a migration file
        ↓
You READ the migration            (ALWAYS — see gotcha in §7)
        ↓
alembic upgrade head
        ↓
DB now matches models. alembic_version updated.
```

**The three-step loop forever after:**
1. Edit model
2. `alembic revision --autogenerate -m "..."`
3. Read it, then `alembic upgrade head`

---

## 4. Initial Setup

### 4.1 Install and initialize

```bash
uv add alembic
uv run alembic init alembic
```

Creates:
```
alembic/
├── env.py
├── script.py.mako
└── versions/
alembic.ini
```

`alembic.ini` and the `alembic/` folder both live at the project root
(same level as `pyproject.toml`).

### 4.2 Edit `alembic.ini`

Comment out the fake URL:

```ini
# sqlalchemy.url = driver://user:pass@localhost/dbname
```

**Why:** We supply the real URL from settings in `env.py`. Leaving this
line active can silently override your real URL — a classic "why is
Alembic trying to connect to `driver://`" bug.

### 4.3 Rewrite `alembic/env.py` for async

The default `env.py` is for sync drivers. Yours is `asyncpg`, so it needs
adapting. Full file:

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 1. Alembic config object
config = context.config

# 2. Logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 3. Import Base + models so Alembic sees them
from app.database.base import Base          # noqa: E402
import app.db_models                        # noqa: F401, E402  ← registers models

# 4. Point Alembic at your models' metadata
target_metadata = Base.metadata

# 5. Load the real DB URL from settings
from app.core.settings import get_settings  # noqa: E402
settings = get_settings()
config.set_main_option("sqlalchemy.url", str(settings.database_url))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

## 5. Why Each Block in `env.py` Matters

| Block | What it does | Why it's needed |
|---|---|---|
| **3** | Imports `Base` + `app.db_models` | Without this, Alembic sees an empty `Base.metadata` and generates nothing. The `import app.db_models` triggers your `__init__.py`, which imports both models. |
| **4** | `target_metadata = Base.metadata` | Tells Alembic which metadata to compare against the DB. Default is `None` — that's why the template "does nothing" out of the box. |
| **5** | `config.set_main_option(...)` | Pushes your real URL into Alembic's config, overriding the `driver://` line. |
| **`do_run_migrations`** | Shared helper | Alembic's async adapter uses `run_sync` to call sync functions — this is that sync function. |
| **`async_engine_from_config`** | Async engine creation | Your DB driver is `asyncpg`. The default sync engine fails. |

### About the `# noqa: E402` comments

`E402` = "module level import not at top of file." In `env.py`, imports
after `config = context.config` are the standard Alembic pattern, but
Ruff flags them. `# noqa` tells Ruff "this is intentional, skip it."

If Ruff isn't configured, the comments are inert — harmless but
unnecessary. Delete them if you don't plan to use Ruff.

---

## 6. Generating and Applying Migrations

### First migration

```bash
uv run alembic revision --autogenerate -m "create users and chatlogs tables"
```

**Expected log output:**
```
INFO  [alembic.autogenerate.compare.tables] Detected added table 'users'
INFO  [alembic.autogenerate.compare.tables] Detected added table 'chatlogs'
...
Generating alembic/versions/xxxx_create_users_and_chatlogs_tables.py ...  done
```

### Read the file before applying

Open `alembic/versions/xxxx_*.py`. You should see:

- `upgrade()` with `op.create_table(...)` for each model
- `downgrade()` with `op.drop_table(...)` in reverse order
- Correct order — child tables (with FKs) created after parents

### Apply

```bash
uv run alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Running upgrade  -> xxxx, create users ...
```

### Verify in Postgres

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

Should show: `alembic_version`, `chatlogs`, `users`.

---

## 7. The Big Gotcha: Always Read the Migration

`--autogenerate` **detects adds and drops**, but it is **not perfect**:

- **Cannot detect column renames** — sees a drop + add (potential data loss!)
- **Misses some server-side changes** (certain defaults, constraints)
- **Never touches data** — only schema

**Discipline:** open the generated file and read it before running
`upgrade head`. If it says `drop_column` and you meant to rename, fix the
migration by hand:

```python
# Alembic generates this (BAD — loses data):
op.drop_column("users", "old_name")
op.add_column("users", sa.Column("new_name", sa.String(50)))

# You should replace it with:
op.alter_column("users", "old_name", new_column_name="new_name")
```

One minute of reading saves you a database restore.

---

## 8. The Postgres Enum Quirk

If a model uses `SQLEnum`, Alembic creates a **Postgres ENUM type**:

```python
sa.Enum('ADMIN', 'USER', 'READONLY', name='role')
```

**Postgres does NOT drop enum types when the table is dropped.** So if
you `downgrade` and then `upgrade` again, you get:

```
ERROR: type "role" already exists
```

**Fix:** explicitly drop the enum in `downgrade()`:

```python
def downgrade() -> None:
    op.drop_index(op.f('ix_chatlogs_user_id'), table_name='chatlogs')
    op.drop_index(op.f('ix_chatlogs_id'), table_name='chatlogs')
    op.drop_table('chatlogs')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
    sa.Enum(name='role').drop(op.get_bind(), checkfirst=True)  # ← add this
```

The `checkfirst=True` makes it safe to run even if the type is already gone.

---

## 9. Command Cheat Sheet

| Command | What it does |
|---|---|
| `alembic revision --autogenerate -m "msg"` | Generate a migration from model changes |
| `alembic revision -m "msg"` | Generate an empty migration (write manually) |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic upgrade +1` | Apply the next one only |
| `alembic downgrade -1` | Roll back the last migration |
| `alembic downgrade base` | Roll back everything |
| `alembic current` | Show the revision the DB is at |
| `alembic history` | List all revisions |
| `alembic heads` | Show the latest revision |

---

## 10. Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| Autogenerate produces empty migration | Models not imported before `Base.metadata` is read | Import `app.db_models` in `env.py` |
| `type "X" already exists` | Postgres enum not dropped | Add `sa.Enum(name='X').drop(op.get_bind(), checkfirst=True)` to `downgrade()` |
| `Target database is not up to date` | Applying a new revision while an old one is unapplied | `alembic upgrade head` first |
| `Can't locate revision identified by 'xxxx'` | The migration file was deleted but `alembic_version` still references it | Delete the row in `alembic_version` and re-run |
| `sqlalchemy.exc.MissingGreenlet` | `env.py` uses sync engine on an async URL | Rewrite `env.py` for async (see §4.3) |
| Autogenerate wants to drop tables you just created | `Base.metadata` is missing some models | Add missing imports to `app/db_models/__init__.py` |
| Duplicate `alembic_version` rows | Multiple heads after parallel branches | `alembic merge heads -m "merge"` |

---

## 11. Best Practices

1. **One migration per logical change.** Don't bundle "add column + new table + rename" into one file.
2. **Commit migrations to git** alongside the model change. They're code, not artifacts.
3. **Never edit an applied migration** in a shared environment. Write a new one.
4. **Always review the downgrade path.** If you can't roll back, you can't safely deploy.
5. **Message should describe the change** — `"add role to users"` not `"update"`.
6. **Run migrations from one place** — a deploy step, not from every app instance at startup.
7. **Test on a fresh database** periodically. Old migrations rot when untested.

---

## 12. When to Run Migrations in Production

| Approach | When it's right |
|---|---|
| **Manual** — SSH in, run `alembic upgrade head` | Small project, one server, low risk |
| **Deploy step** — CI/CD runs it before starting the new app version | Standard practice |
| **Init container / Job** — Kubernetes runs it once before pods start | Kubernetes deployments |
| **At app startup** — every instance runs it | ❌ **Never.** Race conditions, multiple writers |

For your assignment's scaling scenario: run migrations as a **Kubernetes
Job** or **init container** before rolling out the new app version.

---

*Save this file as `docs/alembic-setup.md` in your repo.*