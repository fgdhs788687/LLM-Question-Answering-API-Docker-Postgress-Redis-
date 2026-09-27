from datetime import timedelta, datetime, timezone
from passlib.context import CryptContext
from .settings import get_settings
import jwt

settings = get_settings()
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def hash_password(password: str) -> str:
  return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
  return pwd_context.verify(plain_password, hashed_password)


# Create access token
def create_access_token(data: dict, expire_time: timedelta | None = None) -> str:
  to_encode = data.copy()

  if expire_time:
    expire = datetime.now(timezone.utc) + expire_time
  else:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
  
  to_encode.update({'exp': expire})
  encoded_jwt = jwt.encode(
    to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm
  )
  return encoded_jwt


# Decoding access token:
def decode_access_token(token: str) -> dict | None:
  try:
    payload = jwt.decode(
      token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    return payload
  except jwt.PyJWTError:
    return None # token expire, token invalid, or corrupted token then we will return None