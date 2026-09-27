# SQLAlchemy Models in FastAPI — Complete Reference

How to define database models in FastAPI projects, with both the modern
style and the classic style. Includes the relationship pattern and the
Alembic gotcha that trips everyone up.

---

## 1. Where Models Live

```
app/db_models/
├── __init__.py     # re-exports every model
└── models.py       # the actual model classes
```

Both `User` and `ChatLog` inherit from a shared `Base`:

```python
# app/database/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

The `Base` is what makes them SQLAlchemy models, and its `metadata`
is what Alembic reads to generate migrations.

---

## 2. The `__init__.py` Rule (Important!)

```python
# app/db_models/__init__.py
from app.db_models.models import User, ChatLog

__all__ = ["User", "ChatLog"]
```

**Why this matters:** SQLAlchemy only knows about a model when the
`class X(Base):` line actually **executes**. If nothing imports your
models file, `Base.metadata` is empty and Alembic autogenerate produces
an empty migration.

This file guarantees that **any import of `app.db_models`** pulls in
every model. Your `alembic/env.py` will import it, so Alembic always
sees your tables.

> **Rule:** every model must be imported before Alembic runs. `__init__.py`
> is the natural place for that import.

---

## 3. The Modern Style — `Mapped` + `mapped_column`

SQLAlchemy 2.x's recommended style. Type hints drive nullability.

```python
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
```

**Key trick:** `Mapped[str]` → NOT NULL. `Mapped[str | None]` → nullable.
No need for `nullable=False` — the type hint already says it.

### Pros
- Great IDE autocomplete (`.username` shows as `str`, not `Any`)
- Plays cleanly with Pydantic and FastAPI
- Nullability is self-documenting

### Cons
- Type written twice (hint + column)
- More verbose

---

## 4. The Classic Style — `Column`

The original SQLAlchemy style. Still fully supported. Every tutorial
before ~2022 uses this.

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from app.database.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
```

### Pros
- Faster to write
- Matches every tutorial and Stack Overflow answer you'll find
- Fully supported in 2.x

### Cons
- Weak IDE support — `user.username` shows as `Any`
- Nullability is explicit, so easy to forget `nullable=False`

### Which should you use?
**Either.** For an assignment, pick one and be consistent. Mid-project
migrations are where you lose days.

---

## 5. Common Column Parameters Cheat Sheet

| Parameter | Meaning |
|---|---|
| `primary_key=True` | Unique ID for the row. Auto-increments. |
| `index=True` | Create a DB index — speeds up lookups on this column. |
| `unique=True` | No two rows can share this value. |
| `nullable=False` | Column cannot be NULL. |
| `default=X` | Python-side default. Applied when object is created. |
| `server_default="X"` | DB-side default. Applied even for raw SQL inserts. |
| `String(50)` | VARCHAR(50). **Always set a length** in Postgres. |
| `Text` | Unlimited-length string. Use for questions/answers. |
| `DateTime(timezone=True)` | Timestamp with timezone. **Always use this.** |
| `func.now()` | SQL function — the DB's current time. |

### Defaults — use both when possible

```python
is_active = Column(Boolean, default=True, server_default="true")
```

- `default=True` → Python gets the value immediately when creating `User()`
- `server_default="true"` → DB fills it in even for raw inserts

Bulletproof.

### The `server_default` gotcha

```python
server_default="true"     # ✅ string for boolean
server_default=True       # ❌ sometimes breaks migrations
server_default=func.now() # ✅ for timestamps, use the function
```

For booleans, always use strings.

### The `timezone=True` gotcha

```python
Column(DateTime)                    # ❌ naive — drops tz info
Column(DateTime(timezone=True))     # ✅ stores tz-aware timestamps
```

If you set the value with `datetime.now(timezone.utc)` but the column
is `DateTime` without `timezone=True`, Postgres **silently drops the
timezone**. Always use `timezone=True`.

---

## 6. The Relationship Pattern

Two tables, one-to-many (one user → many chat logs):

```python
# In User
chat_logs = relationship(
    "ChatLog",
    back_populates="user",
    cascade="all, delete-orphan",
)

# In ChatLog
user = relationship("User", back_populates="chat_logs")
```

Rules to remember:

| Rule | Why |
|---|---|
| Class name in the string, not table name | `"ChatLog"` not `"chatlogs"` |
| `back_populates` on **both** sides, matching names | SQLAlchemy validates the pairing |
| `cascade="all, delete-orphan"` on the "one" side | Deleting a user deletes their logs |
| Relationship is not a DB column | It's a Python-only convenience |

Once set up:

```python
user.chat_logs      # list of ChatLog objects
log.user            # the User object
```

---

## 7. Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Class name | Singular, CamelCase | `User`, `ChatLog` |
| Table name | Plural, lowercase | `users`, `chatlogs` |
| Foreign key column | `<table_singular>_id` | `user_id` |
| Index on FK | Yes! | Postgres does **not** auto-index FKs |

### Why singular class names

- `ChatLog(...)` reads as "one log"
- `user.chat_logs` reads as "a list of logs"
- Matches SQLAlchemy docs and most codebases

---

## 8. The Alembic Gotcha

Alembic's autogenerate reads `Base.metadata`. It only knows about
models that have been **imported** in the current process.

If nothing imports `models.py`, autogenerate produces an empty migration
or wants to **drop** your existing tables.

**Fix:** `app/db_models/__init__.py` imports every model, and
`alembic/env.py` does:

```python
from app.database.base import Base
import app.db_models   # ← this triggers __init__.py
target_metadata = Base.metadata
```

Never rely on "something else imports it." Be explicit.

---

## 9. Common Mistakes Checklist

- [ ] `nullable=False` on required columns (or `Mapped[str]` in modern style)
- [ ] `index=True` on `user_id` foreign keys
- [ ] `timezone=True` on every `DateTime` column
- [ ] `server_default="true"` (string) not `True` for booleans
- [ ] `String(N)` with a length, not bare `String`
- [ ] `relationship("ClassName", ...)` uses the class name, not table
- [ ] `__init__.py` re-exports every model
- [ ] The commented-out debug lines removed before submission

---

## 10. When Something Goes Wrong

| Symptom | Likely cause |
|---|---|
| Alembic generates empty migration | Models not imported before `Base.metadata` is read |
| `ImportError: cannot import name 'ChatLog'` | Class name in `__init__.py` doesn't match `models.py` |
| Timestamps come back naive | Missing `timezone=True` on the column |
| FK queries are slow | Missing `index=True` on the FK column |
| `TypeError: relationship() got unexpected keyword` | Typo in `back_populates` (must match exactly on both sides) |

---

*Save this file as `docs/models-setup.md` in your repo.*