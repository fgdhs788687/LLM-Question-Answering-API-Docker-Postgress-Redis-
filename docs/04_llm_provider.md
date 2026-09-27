# LLM Provider Layer in FastAPI — Complete Reference

How to integrate an LLM (Groq, OpenAI, etc.) into a FastAPI project behind
a swappable provider interface. Includes the "why" behind every design
choice and the exact patterns to reuse.

---

## 1. The Big Idea

Never call the LLM directly from your endpoint. Put it behind an
**interface** so you can:

- Test the endpoint without hitting a real LLM
- Swap providers (Groq → OpenAI → Gemini) without touching `/chat`
- Add retry/fallback logic in one place
- Keep the endpoint focused on HTTP concerns, not LLM concerns

**Analogy:** your endpoint is a waiter. The waiter doesn't cook — they
hand the order to the kitchen. The kitchen can change (real chef, mock
chef for rehearsal), but the waiter's job never changes.

---

## 2. The Cast of Characters

| Piece | Role | Analogy |
|---|---|---|
| `LLMResponse` | Box carrying answer + tokens + model | A parcel with a label |
| `LLMProvider` | The contract — "anything that can answer a prompt" | A job description |
| `GroqProvider` | The real worker that calls Groq | The actual chef |
| `MockProvider` | A fake worker for tests | A stand-in actor |
| `get_llm_provider()` | Picks which worker to use | The manager assigning shifts |

---

## 3. The Flow of One Request

```
Endpoint: POST /chat
     │
     │ "I need someone who can answer prompts"
     ▼
get_llm_provider()      ← decides: real Groq? mock?
     │
     │ returns a provider instance
     ▼
await provider.generate("What is FastAPI?")
     │
     │ provider talks to Groq (or returns canned answer)
     ▼
LLMResponse(answer=..., token_used=..., model=...)
     │
     │ endpoint logs to DB, caches in Redis, returns JSON
     ▼
User receives the answer
```

**Key insight:** the endpoint **never mentions Groq**. It only knows
`LLMProvider`. Swapping implementations doesn't touch `/chat`.

---

## 4. The Files

```
app/
├── schemas/
│   └── schemas.py       # LLMResponse
└── services/
    ├── __init__.py
    └── llm.py           # LLMProvider, GroqProvider, MockProvider, get_llm_provider
```

---

## 5. `LLMResponse` — The Return Shape

```python
from pydantic import BaseModel

class LLMResponse(BaseModel):
    answer: str
    token_used: int
    model: str
```

### Why these three fields

- **`answer`** — the LLM's reply text
- **`token_used`** — for logging usage (assignment requirement)
- **`model`** — which model produced it (useful for audit/debug)

### Why NOT `latency_ms`

Latency is **not** the provider's concern. The caller decides *what*
it's measuring (LLM call only? DB write too?). Two sources of truth for
the same number = confusion.

**Rule:** the caller measures latency around `await provider.generate()`.
The provider returns only what it knows.

### Why a Pydantic model instead of a tuple/list

```python
# ❌ Fragile — caller must remember indexes
return [answer, tokens, model]    # is 0 answer or tokens?

# ✅ Self-documenting — caller uses attribute names
return LLMResponse(answer=..., token_used=..., model=...)
result.answer          # clear
result.token_used      # clear
```

Pydantic also plays nicely with FastAPI serialization later.

---

## 6. `LLMProvider` — The Contract

```python
from typing import Protocol

class LLMProvider(Protocol):
    async def generate(self, prompt: str) -> LLMResponse: ...
```

### Why `Protocol` instead of `ABC`

- **`Protocol`** = structural typing. "Anything with this shape counts."
  No inheritance needed. `GroqProvider` and `MockProvider` just *have*
  the method, and that's enough.
- **`ABC`** = requires explicit `class GroqProvider(LLMProvider):`.
  More ceremony for no benefit here.

`Protocol` fits the "duck typing with type-checker support" philosophy.
Perfect for swappable implementations.

### Why the body is `...`

`...` (ellipsis) means "no implementation, just a stub." Idiomatic for
Protocols. `pass` works too but is less expressive.

---

## 7. `GroqProvider` — The Real One

```python
from openai import AsyncOpenAI
from app.schemas.schemas import LLMResponse

class GroqProvider:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    async def generate(self, prompt: str) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return LLMResponse(
            answer=response.choices[0].message.content,
            token_used=response.usage.total_tokens,
            model=self.model,
        )
```

### Key design decisions

**1. Client created once in `__init__`, not per call.**
Creating a new `AsyncOpenAI` per request wastes connection pools.
Reuse the client.

**2. Use the `openai` SDK, not a Groq-specific SDK.**
Groq is OpenAI-API-compatible. Pointing `base_url` at Groq makes the
code portable: swap `base_url` and it works with OpenAI, OpenRouter,
Together, etc. **No other code changes.**

**3. No retry/timeout yet.**
Add these later, inside `generate`, so all providers benefit. Layering
makes debugging easier — verify happy path first.

**4. No latency measurement.**
Caller measures. See §5.

### Why Groq (for this project)

- Fast (custom hardware, ~200–800ms responses)
- OpenAI-compatible API
- Generous free tier (thousands of requests/day)
- `openai/gpt-oss-120b` is a capable open model

---

## 8. `MockProvider` — The Test Double

```python
class MockProvider:
    def __init__(self, answer: str = "mocked answer"):
        self.answer = answer
        self.calls: list[str] = []

    async def generate(self, prompt: str) -> LLMResponse:
        self.calls.append(prompt)
        return LLMResponse(
            answer=self.answer,
            token_used=42,
            model="mock",
        )
```

### Why a mock is essential

Using the real `GroqProvider` in tests means:

| Problem | Consequence |
|---|---|
| **Slow** | 50 tests × 500ms = 25s per run |
| **Flaky** | Groq down = your tests fail |
| **Costly** | Burns your free-tier quota |
| **Non-deterministic** | Can't assert on exact answers |
| **Wrong target** | You're testing Groq, not your code |

### What the mock enables

1. **Determinism** — same answer every run
2. **Speed** — no network, instant
3. **Introspection** — `mock.calls` records what was passed

Example test:

```python
def test_chat_returns_answer():
    mock = MockProvider(answer="FastAPI is a framework")
    app.dependency_overrides[get_llm_provider] = lambda: mock

    client = TestClient(app)
    r = client.post("/chat", json={"question": "What is FastAPI?"})

    assert r.status_code == 200
    assert r.json()["answer"] == "FastAPI is a framework"
    assert mock.calls == ["What is FastAPI?"]   # proves the prompt passed through
```

### The flight simulator analogy

- **Real plane** = GroqProvider. Correct, but expensive, dangerous to
  practice on, can't reset mid-crash.
- **Simulator** = MockProvider. Same controls, same interface, deterministic.
  Practice any scenario hundreds of times for free.

You still fly the real plane (integration tests), but 95% of training
happens in the simulator.

### When to use the real provider in tests

Almost never. Only for **integration tests** — separately marked, run
on demand, verify "Groq is reachable." The default test suite uses mocks.

---

## 9. `get_llm_provider()` — The Factory

```python
from typing import Annotated
from fastapi import Depends

def get_llm_provider() -> LLMProvider:
    return GroqProvider(
        base_url=settings.llm_base_url,
        api_key=settings.groq_api_key,
        model=settings.llm_model,
    )

LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]
```

### Why a function, not a module-level instance

```python
# ❌ Anti-pattern
provider = GroqProvider(...)               # runs at import time
LLMProviderDep = Annotated[..., Depends(provider)]   # Depends wants callable
```

Two problems:
1. `Depends(provider)` requires a **callable**, not an instance. FastAPI
   calls the dependency per request.
2. Module-level construction means importing the module builds a client.
   Breaks clean tests.

### Why build inside the function

FastAPI calls `get_llm_provider()` **once per request**. That's the right
place to construct a provider. The `GroqProvider.__init__` is cheap (it
just stores config; the client is lazy).

If construction ever gets expensive, add `@lru_cache` to
`get_llm_provider`.

### The `Annotated` pattern

```python
LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]
```

Endpoint becomes:

```python
@app.post("/chat")
async def chat(provider: LLMProviderDep, ...):
    ...
```

No `Depends(get_llm_provider)` noise in every signature.

### Override in tests

```python
app.dependency_overrides[get_llm_provider] = lambda: MockProvider()
```

FastAPI swaps the dependency. Production code unchanged.

---

## 10. Using It in an Endpoint

```python
import time
from fastapi import APIRouter

router = APIRouter()

@router.post("/chat")
async def chat(question: str, provider: LLMProviderDep):
    t0 = time.perf_counter()
    result = await provider.generate(question)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    # log to DB, cache in Redis, return JSON
    return {
        "answer": result.answer,
        "model": result.model,
        "token_used": result.token_used,
        "latency_ms": latency_ms,
    }
```

**Notice:** the endpoint measures latency (its job), and the provider
only reports answer/tokens/model.

---

## 11. Testing the Provider in Isolation

A script to hit the real provider without FastAPI:

```python
import asyncio
from app.services.llm import get_llm_provider

async def main():
    provider = get_llm_provider()
    result = await provider.generate("What is FastAPI?")
    print(result.answer)
    print(result.token_used)
    print(result.model)

if __name__ == "__main__":
    asyncio.run(main())
```

Run with:
```bash
uv run python -m scripts.test_provider
```

**Rule:** type aliases like `LLMProviderDep` are FastAPI-only. Outside
FastAPI, call `get_llm_provider()` directly.

---

## 12. Common Mistakes

| Mistake | Why it's wrong | Fix |
|---|---|---|
| `base_url=settings.database_url` | Sends LLM requests to Postgres | Use `settings.llm_base_url` |
| `int(time.perf_counter() - t0) * 1000` | `int()` before `*1000` truncates to 0 | `int((time.perf_counter() - t0) * 1000)` |
| Returning a list/tuple | Caller must remember indexes | Return `LLMResponse` |
| Provider measures latency | Two sources of truth | Caller measures |
| `client = AsyncOpenAI(...)` inside `generate` | New pool per request | Create in `__init__` |
| `Depends(provider_instance)` | `Depends` wants a callable | `Depends(get_llm_provider)` |
| Calling `provider.generate(prompt)` without `await` | Returns coroutine, nothing runs | `await provider.generate(prompt)` |
| `asyncio.run()` per loop iteration | Creates new event loop each time | One `asyncio.run()` at top level |
| Using real provider in unit tests | Slow, flaky, costly | Use `MockProvider` |

---

## 13. Swapping Providers — The Payoff

Because the endpoint depends on `LLMProvider`, not `GroqProvider`,
changing providers is one file:

```python
# app/services/llm.py
def get_llm_provider() -> LLMProvider:
    return OpenAIProvider(...)   # was GroqProvider
```

Nothing else changes. Not the endpoint, not the tests, not the schemas.

**This is the entire point of the provider interface.** It's what the
assignment calls "LLM Gateway" — a single, swappable seam between your
app and any LLM backend.

---

## 14. What's Still Missing (Add Later)

| Feature | Where it goes | Why |
|---|---|---|
| **Timeout** | `GroqProvider.__init__` (client) | Fail fast if LLM hangs |
| **Retry with backoff** | Inside `GroqProvider.generate` | Handle transient 429/5xx |
| **Fallback model** | Inside `GroqProvider.generate` | If primary model fails, try secondary |
| **Rate limiting** | Endpoint or middleware (Redis) | Protect Groq quota |
| **Caching** | Endpoint or middleware (Redis) | Avoid duplicate LLM calls |
| **Circuit breaker** | Wrapper around `generate` | Stop hammering a failing provider |

Each is isolated. None requires touching the others. That's the benefit
of clean layering.

---

## 15. Quick Checklist

- [ ] `LLMResponse` with `answer`, `token_used`, `model`
- [ ] `LLMProvider` as a `Protocol`
- [ ] `GroqProvider` builds client in `__init__`, `generate` awaits completion
- [ ] `MockProvider` records calls, returns canned response
- [ ] `get_llm_provider()` returns a `GroqProvider`
- [ ] `LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]`
- [ ] Verified with standalone script before wiring `/chat`
- [ ] Tests use `app.dependency_overrides` to swap in `MockProvider`

---

*Save this file as `docs/llm-provider.md` in your repo.*