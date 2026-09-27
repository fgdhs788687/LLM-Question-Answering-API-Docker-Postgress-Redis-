from fastapi import HTTPException, Depends, status
from app.core.security import decode_access_token
from app.db_models.models import User
from fastapi.security import OAuth2PasswordBearer
from app.database.deps import DbSession
from sqlalchemy import select
from typing import Annotated

oauth_schema = OAuth2PasswordBearer(tokenUrl='/auth/login')
Tokendep = Annotated[str, Depends(oauth_schema)]

async def get_current_user(token: Tokendep, db: DbSession) -> User:
  creadential_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate the creadentials",
    headers={
      "WWW-Authenticate":"Bearer"
    }
  )

  payload = decode_access_token(token)
  if payload is None:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Token"
  )

  user_id_str = payload.get('sub')
  if user_id_str is None:
    raise creadential_exception


  try:
    user_id_int = int(user_id_str)
  except (ValueError, TypeError):
    raise creadential_exception

  result = await db.execute(select(User).where(User.id == user_id_int))
  user = result.scalar_one_or_none()
  if user is None: raise creadential_exception
  if not user.is_active: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Inactive User')
  
  return user

# The Depedency to be used in the endpoint or route
# This will be used to get the current user
CurrentUser = Annotated[User, Depends(get_current_user)]
