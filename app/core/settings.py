from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, RedisDsn, SecretStr
from functools import lru_cache

class Settings(BaseSettings):
  groq_api_key: SecretStr 
  llm_base_url: str
  llm_model: str = "openai/gpt-oss-120b"

  database_url: PostgresDsn
  redis_url: RedisDsn

  jwt_secret: str
  jwt_algorithm: str = 'HS256'
  jwt_expire_minutes: int = 60

  model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore" # Ignore's the extra .env variable without causing a crash.
  )

@lru_cache
def get_settings() -> Settings:
  return Settings()

# Example:
# s = get_settings()
# s.groq_api_key.get_secret_value() to get the secret key or api key
# Use s.groq_api_key.get_secret_value() where you need the raw value