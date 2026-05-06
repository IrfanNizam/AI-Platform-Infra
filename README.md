# AI Platform Infra

A self-hosted AI platform infrastructure built to demonstrate production-grade patterns for running agentic applications. Routes LLM requests through a centralised gateway, traces every call for observability, and exposes infrastructure metrics for real-time monitoring — all running locally on Docker Compose at zero cost.

---

## What this is

This project is the **platform layer** for AI applications. The demo-app represents an agentic application — it has the agent logic, the goals, the steps. LiteLLM sits beneath it as the AI gateway, handling model selection, fallback routing, and token tracking transparently.

The separation matters: the application developer writes agent logic, the platform engineer owns everything below — and that boundary is exactly what this project demonstrates.

```
┌─────────────────────────────────────────────┐
│              agentic application             │
│                  demo-app                    │  ← agent logic lives here
└─────────────────────┬───────────────────────┘
                      │
┌─────────────────────▼───────────────────────┐
│              AI API gateway                  │
│                  LiteLLM                     │  ← platform layer starts here
│    routing · fallback · token budgets        │
└──────────┬──────────────────────┬───────────┘
           │                      │
┌──────────▼──────┐    ┌──────────▼──────────┐
│ gemini-3-flash  │    │ gemini-3.1-flash     │
│ (primary)       │    │ -lite (fallback)     │
└─────────────────┘    └─────────────────────┘

┌─────────────────────────────────────────────┐
│              observability                   │
│  Langfuse (LLM traces) · Prometheus · Grafana│
└─────────────────────────────────────────────┘
```

---

## Architecture

| Service | Port | Purpose |
|---|---|---|
| demo-app | 8000 | Sample FastAPI agentic app — calls LiteLLM gateway |
| LiteLLM | 4000 | AI API gateway — model routing, fallback, token tracking |
| Langfuse | 3100 | LLM observability — traces every request, response, token usage, latency |
| Prometheus | 9090 | Scrapes infra metrics from LiteLLM every 15 seconds |
| Grafana | 3001 | Visualises Prometheus metrics — request rates, token usage, errors |
| Postgres | 5432 | Shared database — two isolated DBs: `langfuse` and `devdb` |

## Design Considerations

**Observability at the gateway, not the application** — Langfuse and 
Prometheus are wired into LiteLLM, not the demo-app. Any application 
calling the gateway gets full tracing and metrics without any code changes. 
This keeps observability a platform concern, not an application concern.

**Gateway pattern for LLM traffic** — LiteLLM applies the same patterns 
used in traditional API infrastructure (rate limiting, fallback routing, 
cost tracking) to LLM traffic. Swapping models or adding providers requires 
zero application changes.

### Key design decisions

**Gateway-level observability** — Langfuse traces and Prometheus metrics are wired at the LiteLLM layer, not the application layer. The demo-app has zero observability code. Any application that calls LiteLLM gets full tracing automatically.

**Multi-model fallback** — LiteLLM routes to `gemini-3-flash-preview` as primary. If it fails or rate-limits, it automatically falls back to `gemini-3.1-flash-lite-preview`. The calling application never needs to handle this.

**Single Postgres, two databases** — LiteLLM and Langfuse each get an isolated database inside one Postgres container. An `init.sql` script creates both databases automatically on first start — no manual setup needed.

**Pinned image versions** — all services use pinned versions (`litellm:v1.83.10-stable`, `prometheus:v3.4.0`, `grafana:11.6.1`, `postgres:16-alpine`) to avoid silent breaking changes.

**Healthcheck-gated startup** — Postgres must pass `pg_isready` before LiteLLM or Langfuse start. LiteLLM must pass its liveliness check before demo-app starts. No race conditions on cold start.

---

## Prerequisites

- **WSL2** (Windows) or native Linux/macOS terminal
- **Docker Desktop** — allocate at least 4GB RAM in settings
- **Python 3.12+** (for running demo-app outside Docker during development)
- **Gemini API key** — free, no credit card: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

---

## Running locally

**1. Clone the repo**

```bash
git clone https://github.com/IrfanNizam/AI-Platform-Infra.git
cd AI-Platform-Infra
git checkout feature/dev
```

**2. Configure environment variables**

```bash
cp .env.example .env
```

Open `.env` and fill in the required values. Generate the three secrets with:

```bash
openssl rand -hex 32
```

**3. Start the stack**

```bash
docker compose up -d
```

Services start in dependency order, gated by healthchecks. Allow ~30-60 seconds for all services to become healthy.

**4. Verify**

```bash
docker compose ps
```

All services should show `running (healthy)`.

**5. Make your first request**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"content": "What is Kubernetes in one sentence?"}'
```

Then open Langfuse at `http://localhost:3100` — the trace appears automatically.

---

## Service UIs

| UI | URL | Default credentials |
|---|---|---|
| Demo app (Swagger) | http://localhost:8000/docs | — |
| LiteLLM gateway | http://localhost:4000/ui | Set via `LITELLM_MASTER_KEY` |
| Langfuse traces | http://localhost:3100 | Set via `LANGFUSE_USER_EMAIL` / `LANGFUSE_USER_PASSWORD` |
| Grafana | http://localhost:3001 | admin / admin |
| Prometheus | http://localhost:9090 | — |

---

## LLM routing

| Model alias | Provider model | Role |
|---|---|---|
| `gemini-flash` | `gemini/gemini-3-flash-preview` | Primary |
| `gemini-flash-fallback` | `gemini/gemini-3.1-flash-lite-preview` | Automatic fallback |

Fallback is handled at the router level in `litellm/config.yaml`. When the primary model hits rate limits or returns an error, LiteLLM retries on the fallback transparently. The demo-app always calls `gemini-flash` — it never needs to know a fallback occurred.

---

## Observability

**Langfuse** traces every LLM call automatically via LiteLLM's `success_callback`. Each request shows:
- Full prompt and response
- Token usage and estimated cost
- Latency breakdown
- Model used (including whether fallback was triggered)

For agentic workloads with multiple chained LLM calls, each step appears as a span inside a single trace — making it straightforward to detect logic loops or runaway agents.

**Prometheus** scrapes `/metrics` from LiteLLM every 15 seconds. Key metric to start with in Grafana:

```
litellm_deployment_total_requests_total
```

---

## Useful commands

```bash
# Start everything
docker compose up -d

# Follow logs for a specific service
docker compose logs -f litellm

# Restart a single service after config change (e.g. litellm/config.yaml)
docker compose restart litellm

# Stop everything — preserves data volumes
docker compose down

# Full reset including all data
docker compose down -v
```

---

## How this relates to agentic AI

This project is the **infrastructure layer** that agentic applications run on top of. Real agentic frameworks like LangGraph, CrewAI, or AutoGen can be pointed at the LiteLLM gateway as their LLM backend. They immediately get:

- Automatic fallback if a model fails mid-task
- Token budget enforcement to prevent runaway cost
- Full trace visibility per agent run in Langfuse
- Infrastructure metrics across all agent workloads in Grafana

The agent developer writes the logic. The platform layer handles reliability, observability, and cost control.

---

## Roadmap

- [ ] Migrate to k3s with Helm charts
- [ ] GitHub Actions CI/CD pipeline — build, scan, deploy
- [ ] JFrog Artifactory for container supply chain security
- [ ] Add Ollama as a local offline fallback provider
- [ ] Per-project token budgets and chargeback via LiteLLM virtual keys
- [ ] Frontend UI for demo-app
- [ ] Harden secrets — move from `.env` to a proper secrets manager

---