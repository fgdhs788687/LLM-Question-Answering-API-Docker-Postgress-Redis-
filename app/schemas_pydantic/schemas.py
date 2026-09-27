from pydantic import BaseModel
from datetime import datetime

class LLMResponse(BaseModel):
  answer: str
  tokens_used: int
  model: str

# User-Schemas:
class UserCreate(BaseModel):
  username: str
  password: str

class UserOut(BaseModel):
  id: int
  username: str
  role: str
  is_active: bool
  created_at: datetime


# Token-Schemas:
class TokenResponse(BaseModel):
  access_token: str
  token_type: str = "bearer"


# Chat-Schemas:
class ChatRequest(BaseModel):
  question: str


class ChatResponse(BaseModel):
  answer: str
  model: str
  tokens_used: int
  latency_ms: int
  cached: bool