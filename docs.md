---
title: "Docs — HiveGate"
description: "Architecture, API reference, configuration, and operational guide for HiveGate."
permalink: /docs/
---

# Documentation

A condensed, link-out-rich overview. Full source-of-truth is the
[README in `hivegate-ai/hivegate`](https://github.com/hivegate-ai/hivegate#readme) and the
[interactive `/docs` page](http://localhost:8000/docs) on your running instance.

## Architecture {#architecture}

```
┌─────────────────────────────────────────────────────────────────┐
│  Client (web, CLI, IDE)                                         │
└─────────────────────────────────┬───────────────────────────────┘
                                  │  HTTPS / X-API-Key
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  HiveGate (FastAPI)                                             │
│                                                                 │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────────────────┐  │
│  │ /v2/agents  │  │ /v2/teams  │  │ /v2/{prompts,knowledge,…}│  │
│  └──────┬──────┘  └─────┬──────┘  └──────────────┬───────────┘  │
│         └─────────┬─────┘                        │              │
│                   ▼                              ▼              │
│         ┌─────────────────┐         ┌──────────────────────┐    │
│         │ Agno runtime    │         │ Supervisor / Workers │    │
│         │ (LLM, tools,    │         │ (Docker, K8s)        │    │
│         │  sessions)      │         └──────────────────────┘    │
│         └────────┬────────┘                                     │
└──────────────────┼──────────────────────────────────────────────┘
                   │
       ┌───────────┼─────────────┐
       ▼           ▼             ▼
   PostgreSQL   Qdrant        LLM provider
   (agents,     (knowledge   (OpenAI, Gemini,
    sessions,    vectors)     Anthropic, …)
    tokens,
    queue)
```

## API reference {#api}

All endpoints are documented on a running instance at `/docs` (OpenAPI). Summary:

| Resource | Endpoint | Purpose |
|---|---|---|
| Agents | `GET/POST /v2/agents` | List, create, update, delete agents |
| Agent chat | `POST /v2/agents/{id}/chat` | Chat with an agent (stream or non-stream) |
| Teams | `GET/POST /v2/teams` | List, create, update, delete teams |
| Team run | `POST /v2/teams/{id}/runs` | Execute a team |
| Knowledge | `GET/POST /v2/knowledge/{tenant_id}` | Manage per-tenant knowledge entries |
| Tokens | `GET/POST /v2/users/{user_id}/tokens` | OAuth token storage with auto-refresh |
| Prompts | `GET/POST /v2/prompts` | Versioned prompt templates |
| Skills | `GET/POST /v2/skills` | Reusable skill definitions |
| Engines | `GET/POST /v2/engines` | Supervisor execution engines |
| Targets | `GET/POST /v2/targets` | Supervisor run targets |
| Approvals | `GET/POST /v2/approvals` | Pending approval review |
| Admin | `GET/POST /admin/*` | API keys, cache management |

### Authentication

- `X-API-Key: agw_xxxxx` for `/v2/*`
- `X-Admin-Secret: ...` for `/admin/*`
- `AUTH_DISABLED=true` for local development

## Configuration {#config}

Core environment variables — full list in the [README](https://github.com/hivegate-ai/hivegate#environment-variables):

| Variable | Required | Purpose |
|---|---|---|
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASS` / `DB_DATABASE` | Yes | Postgres |
| `ADMIN_SECRET` | Yes (prod) | Admin endpoint auth |
| `GOOGLE_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | At least one | LLM provider |
| `QDRANT_URL` | No | Vector DB for knowledge |
| `PROMPT_STORAGE_BACKEND` | No | `postgres` (default) or `service` |
| `OTEL_TRACING_BACKEND` / `OTEL_LOGGING_BACKEND` | No | `console`, `otlp`, `sentry`, `logtail` |
| `AUTH_DISABLED` | No | Dev only — bypass auth |

## Toolkits {#toolkits}

| Toolkit | Providers | Tools |
|---|---|---|
| CalendarToolkit | Google Calendar, Microsoft Calendar | schedule_meeting, list_events, cancel_meeting |
| EmailToolkit | Gmail, Outlook | send_email, search_emails, create_draft |
| ContactsToolkit | Google Contacts, Microsoft Contacts | create_contact, search_contacts, list_contacts |
| DriveToolkit | Google Drive, OneDrive | list_files, read_file, upload_file |

All toolkits ship with confirmation-based workflows (user reviews before execution) and OAuth token management with auto-refresh.

Detail: [`toolkits/README.md`](https://github.com/hivegate-ai/hivegate/blob/main/toolkits/README.md).

## Supervisor platform {#supervisor}

Multi-agent execution with classification, job queues, approval flows, and containerized workers. Workers can run as Docker containers or Kubernetes pods, fed by an in-Postgres job queue.

Detail in the [README](https://github.com/hivegate-ai/hivegate#supervisor-platform) and `supervisor/`, `remote_agent/`.

## Database schema {#schema}

| Schema | Tables | Purpose |
|---|---|---|
| `public` | `agent_info`, `team_info`, `team_agent`, `knowledge_entries`, `user_tokens`, `api_keys`, `token_usage` | Core data |
| `prompts` | `prompts` | Prompt templates |
| `ai` | (auto-created by Agno) | Agent sessions & memories |

Migration: `db/migrations/setup.sql`. Auto-applied on `docker compose up`.

## Observability {#observability}

OpenTelemetry-based, pluggable. Set `OTEL_TRACING_BACKEND` and `OTEL_LOGGING_BACKEND`:

```sh
# Sentry
OTEL_TRACING_BACKEND=sentry
SENTRY_DSN=https://xxx@sentry.io/xxx

# Cloud-native OTLP
OTEL_TRACING_BACKEND=otlp
OTEL_LOGGING_BACKEND=otlp
OTEL_OTLP_ENDPOINT=http://collector:4317
```

## Development {#development}

```sh
./scripts/dev_setup.sh           # Create venv + install deps
source .venv/bin/activate
./scripts/run_validate.sh        # Format, lint, type-check
pytest tests/v2/                 # Tests
./scripts/generate_requirements.sh upgrade   # Bump deps
```

## Detailed reference {#detailed}

Per-endpoint and per-subsystem deep dives (synced at build time from
[`hivegate-ai/docs`](https://github.com/hivegate-ai/docs)):

**Getting started**
- [Overview](/docs/overview/) — architecture and key concepts
- [Quickstart](/docs/quickstart/) — setup and first API call
- [Authentication](/docs/authentication/) — API keys, admin auth, dev mode
- [Configuration](/docs/configuration/) — environment variables

**API reference**
- [Agents](/docs/api-agents/) — `/v2/agents` CRUD and chat
- [Teams](/docs/api-teams/) — coordinate + supervisor team modes
- [Prompts](/docs/api-prompts/) — versioned prompt templates
- [Knowledge](/docs/api-knowledge/) — tenant + collection-level
- [Tokens](/docs/api-tokens/) — OAuth token storage
- [Skills](/docs/api-skills/) — reusable skill definitions
- [Engines](/docs/api-engines/) — execution engine registry
- [Targets](/docs/api-targets/) — execution target registry
- [Approvals](/docs/api-approvals/) — HITL approval flow
- [Admin](/docs/api-admin/) — cache, API keys, background tasks

**Supervisor platform**
- [Architecture](/docs/supervisor-platform/) — classification, worker types
- [Agent packs](/docs/agent-packs/) — YAML pack format, CLI
- [Remote agent](/docs/remote-agent/) — Docker/K8s container execution
- [Toolkits](/docs/toolkits/) — Calendar, Email, Drive, ClaudeCode, ManagedAgents

**Reference**
- [Models](/docs/models-reference/) — Pydantic request/response models
- [Database schema](/docs/database-schema/) — all tables
- [LLM models](/docs/llm-models/) — supported OpenAI, Gemini, Claude variants
- [Deployment](/docs/deployment/) — docker-compose, production setup
- [Development](/docs/development/) — dev setup, validation, testing

## Support

- [Issue tracker](https://github.com/hivegate-ai/hivegate/issues)
- [Agno docs](https://docs.agno.com)
- [Deploy guide](/deploy/)
