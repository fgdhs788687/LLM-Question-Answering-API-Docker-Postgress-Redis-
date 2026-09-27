from typing import AsyncGenerator, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.db import AsyncSessionLocal
from fastapi import Depends

async def get_db() -> AsyncGenerator[AsyncSession, None]:
  async with AsyncSessionLocal() as session:
    try:
      yield session
    except Exception:
      await session.rollback()
      raise
    finally:
      await session.close()

# This is the Dependency for the Database Session:
DbSession = Annotated[AsyncSession, Depends(get_db)]