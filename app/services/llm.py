import asyncio
from openai import AsyncOpenAI
from app.schemas_pydantic.schemas import LLMResponse
from typing import Protocol
from app.core.settings import get_settings
settings = get_settings()

# (Protocol)
# Declaring a Protocol which the LLMProvider class must implement:
class LLMProvider(Protocol):
  async def generate(self, prompt: str) -> LLMResponse:
    pass

# (Endpoint)
# Following the LLMProvider class and 
class GroqProvider:
  def __init__(self, base_url: str, api_key: str, model: str):
    self.client = AsyncOpenAI(
      base_url=base_url,
      api_key=api_key
    )
    self.model = model

  async def generate(self, prompt: str) -> LLMResponse:
    response = await self.client.chat.completions.create(
      model=self.model,
      messages=[{'role':'user','content':prompt}]
    )

    return LLMResponse(
      answer=response.choices[0].message.content,
      tokens_used=response.usage.total_tokens,
      model=self.model,
  )

# (Pytest and httpx)
# This will be used for testing that's all:
class MockProvider:
  def __init__(self, answer: str = "mocked answer"):
    self.answer = answer
    self.calls: list[str] = [] # an empty list to store all the questions

  async def generate(self, prompt: str) -> LLMResponse:
    self.calls.append(prompt) # appends the asked question to the list
    return LLMResponse(
      answer = self.answer,
      tokens_used=42,
      model='mock',
    )

# (Endpoint)
# We will import this to the file where the endpoint is present to use:
from typing import Annotated
from fastapi import Depends

# For Endpoint:
def get_llm_provider() -> LLMProvider:
  return GroqProvider(
    base_url=settings.llm_base_url, api_key=settings.groq_api_key.get_secret_value(), model=settings.llm_model
  )

LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]
