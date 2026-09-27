from sqlalchemy.ext.asyncio import (
  create_async_engine,
  AsyncSession,
  async_sessionmaker
)
from app.core.settings import get_settings

settings = get_settings()

engine = create_async_engine(
  str(settings.database_url),           # PostgresDsn -> str()
  echo=False,                           # True = log for every SQL (great for debuging)
  pool_size=5,                          # 5 conncetion's kept open
  max_overflow=10,                      # extra connection's allowed under the load
  pool_pre_ping=True,                   # checks connection is alive before use
  connect_args={"ssl":"require"},       # ssl handled here not in url
)

AsyncSessionLocal = async_sessionmaker(
  bind=engine,
  class_=AsyncSession,
  expire_on_commit=False,
  autoflush=False
)