from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.core.security import create_access_token, hash_password, verify_password
from app.database.deps import DbSession
from app.db_models.models import Role, User
from app.schemas_pydantic.schemas import TokenResponse, UserCreate, UserOut
from app.api.user_deps import CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])

# User Logins:
@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=access_token, token_type="bearer")

# Registering the user:
@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def register(user: UserCreate, db: DbSession):
    result = await db.execute(select(User).where(User.username == user.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    new_user = User(
        username=user.username,
        hashed_password=hash_password(user.password),
        role=Role.USER,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.get('/me', response_model=dict)
async def me(current_user: CurrentUser):
    return {'User': current_user.username, 'status': 'Logged In'}