from app.database.base import Base

from sqlalchemy import (
  Column, Integer, String, Boolean, 
  DateTime, ForeignKey, Text, Enum as SQLEnum
)

from enum import Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from sqlalchemy.sql import func

class Role(str, Enum):
    ADMIN = 'admin'
    USER = 'user'
    READONLY = 'readonly'

class User(Base):
  __tablename__ = "users"

  id = Column(Integer, primary_key=True, index=True)
  username = Column(String(50), unique=True, nullable=False, index=True)
  hashed_password = Column(String(255), nullable=False)
  role = Column(SQLEnum(Role), default=Role.USER, nullable=False)
  is_active = Column(Boolean, nullable=False, default=True, server_default='true')
  # created_at = Column(DateTime(timezone=True), default= lambda: datetime.now(timezone.utc)) its a normal way
  created_at = Column(
    DateTime(timezone=True),
    server_default=func.now(),
    nullable=False
  )

  chat_logs = relationship(
    'ChatLog',
    back_populates='user',
    cascade="all, delete-orphan" # When a user is deleted all his/her chatlogs also are deleted
  )

class ChatLog(Base):
  __tablename__ = "chatlogs"

  id = Column(Integer, primary_key=True, index=True)
  user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
  question = Column(Text, nullable=False)
  answer = Column(Text, nullable=False)
  model = Column(String(100), nullable=False, default="openai/gpt-oss-120b")
  tokens_used = Column(Integer, nullable=False, default=0)
  latency_ms = Column(Integer, nullable=False, default=0)
  cached = Column(Boolean, nullable=False, default=False, server_default='false')
  # created_at = Column(DateTime(timezone=True), default= lambda: datetime.now(timezone.utc))
  created_at = Column(
    DateTime(timezone=True),
    server_default=func.now(),
    nullable=False
  )

  user = relationship(
    'User',
    back_populates='chat_logs'
  )