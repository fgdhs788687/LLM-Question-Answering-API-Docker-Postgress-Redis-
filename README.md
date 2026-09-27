backend/README.md

# LLM Q&A API

## Overview
- One paragraph: what it does, who it's for

## Architecture
- ASCII or Mermaid diagram: Users → LB → FastAPI → Redis/Queue → LLM Gateway → LLM APIs
- One paragraph explaining the flow

## Tech Stack
- FastAPI, PostgreSQL (Neon), Redis, Groq (openai/gpt-oss-120b), SQLAlchemy 2.x async, Alembic, Docker

## Setup Instructions
- Prerequisites: Python 3.12, uv, Docker
- Steps: clone, cp .env.example .env, fill in keys, uv sync, alembic upgrade head, uv run uvicorn ...

## API Endpoints

### POST /auth/login
- Request/response example

### POST /chat
- Request/response example
- Auth: Bearer token required

### GET /health
### GET /metrics

## Design Decisions
- Why Groq (free, fast, OpenAI-compatible)
- Why a provider interface (testability, swappability)
- Why Redis (cache + rate limiting) — even if not implemented, say so
- Why async SQLAlchemy
- Why JWT (stateless, scales horizontally)

## Scaling — 100 to 500 RPS
- Horizontal scaling: N FastAPI instances behind a load balancer
- Kubernetes HPA: scale on CPU + request queue depth
- Redis: cache identical questions (TTL 1h), distributed rate limiting
- Background queues (Celery/RQ): for long-running LLM calls under load
- LLM API limits: Groq's RPM/TPM caps → batch, cache, degrade gracefully
- Concurrency: async I/O, connection pooling per instance
- Failure recovery: retries with exponential backoff, timeout, fallback model, circuit breaker

## Migration Scenario — 1 EC2 → 10,000 users
- Step 1: Containerize (Docker) → move off single EC2
- Step 2: Load balancer (ALB) in front of 2+ instances
- Step 3: Move to ECS or EKS for orchestration
- Step 4: Managed Postgres (RDS), managed Redis (ElastiCache)
- Step 5: Add queue + worker for long-running LLM calls
- Step 6: Monitoring (CloudWatch + Prometheus/Grafana)
- Minimal downtime: blue/green deploy, DB migrations run as a job before rollout
- Secrets: AWS Secrets Manager, injected as env vars

## SSO / OIDC Extension
- Current: local username/password + JWT
- Production: Application → SSO/OAuth2/OIDC → Identity Provider (Okta/Auth0/Azure AD) → JWT → API Gateway → AI Service
- The app never stores passwords; the IdP verifies identity and issues a JWT; the API just validates the signature

## RBAC
- Admin: manage users, access /metrics, view all chat logs
- User: /chat only, sees own logs
- Read-only: access permitted reports/data, cannot /chat
- Implemented via a role claim in JWT + a dependency that enforces required role

## What's Implemented vs Designed
- ✅ Implemented: auth, /chat, DB logging, LLM provider, health, Docker config
- 📝 Designed but not built: Redis cache, rate limiter, /metrics, queue-based async chat, tests
- Why: deadline constraints; design is documented and can be implemented incrementally

## Repository Structure
- Tree of the app/ folder

## Running Tests
- uv run pytest

## Loom Video
- Link