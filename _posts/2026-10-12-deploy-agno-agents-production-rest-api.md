---
title: "Deploying Agno agents to production as a REST API"
description: "How to serve Agno agents over HTTP with per-user sessions, Postgres-backed history, API keys and a one-click Docker deploy, and when AgentOS is enough."
date: 2026-10-12
---

An [Agno](https://github.com/agno-agi/agno) agent that works in a script is a few lines of Python. Turning it into something a web or mobile app can call for thousands of users takes more: an HTTP endpoint, a conversation per user, history that survives restarts, API keys, model keys kept on the server, and a container you can deploy.

This post shows how [HiveGate](https://github.com/hivegate-ai/hivegate), an MIT-licensed FastAPI service built on Agno, handles each of those. It also covers when you should skip HiveGate and use Agno's own AgentOS.

## First: you may not need HiveGate

Agno ships [AgentOS](https://docs.agno.com/agent-os/introduction), which serves agents defined in code over HTTP, with sessions, human approval, RBAC and tracing:

```python
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.google import Gemini
from agno.os import AgentOS

support_agent = Agent(
    name="support-agent",
    model=Gemini(id="gemini-3-flash-preview"),
    db=PostgresDb(db_url="postgresql+psycopg://ai:ai@localhost:5432/ai"),
    add_history_to_context=True,
)

app = AgentOS(agents=[support_agent]).get_app()
```

If your agents live in your codebase and that covers what you need, use AgentOS. It's maintained by the Agno team and tracks Agno releases.

HiveGate is for a different case: agents that act *for your users* in their own Google or Microsoft accounts, and agents, prompts and skills that you manage as data through an API instead of shipping code for each change.

## Agents are records, not code

In HiveGate you create an agent with a POST. The `template` becomes the agent's system prompt, stored as a versioned prompt in Postgres. The `config` block maps onto Agno's `Agent` options.

```sh
curl -X POST http://localhost:8000/v2/agents \
  -H "X-API-Key: $HIVEGATE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "support-agent",
    "name": "support-agent",
    "template": "You are the support assistant for Acme. Answer briefly and cite the help center when you can.",
    "description": "Customer support for Acme",
    "tags": ["available_tools:email,calendar"],
    "config": {
      "enable_memory": true,
      "enable_history": true,
      "num_history_runs": 3
    }
  }'
```

The `available_tools:` tag switches on HiveGate's built-in toolkits for this agent. Leave it out and the agent gets none of them. Agents that need other tools can point at MCP servers over Streamable HTTP through `config.worker_config.mcp_servers`.

Changing the prompt later is a `PUT /v2/prompts/support_agent` (the prompt ID is the agent's name in snake case). The next chat picks up the new template, so a prompt fix doesn't need a redeploy.

## Chatting, with sessions per user

Every chat request names a `user_id` and a `session_id`. Both are required, as are `timezone` and `locale`:

```sh
curl -X POST http://localhost:8000/v2/agents/support-agent/chat \
  -H "X-API-Key: $HIVEGATE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "My invoice from last month looks wrong.",
    "user_id": "user-1842",
    "session_id": "ticket-5521",
    "timezone": "America/New_York",
    "locale": "en-US",
    "stream": false
  }'
```

The non-streaming response is a JSON object with `content`, `session_id`, `run_id`, `status`, the `tools` the agent called, and `token_usage` for that call.

Here is what happens to those two IDs:

- **History.** Agno stores each run in a Postgres session table, one table per agent. With `enable_history` on, the last `num_history_runs` runs of the same session go back into the model's context. A follow-up with the same `session_id` continues the conversation, even after a restart or on another replica.
- **Memory.** With `enable_memory` on, Agno's memory manager keeps facts about the user across sessions, keyed by `user_id`.
- **Agent cache.** HiveGate builds the Agno `Agent` once per (prompt, agent, model, user, session) and caches it in the process, so later turns skip setup.

Per-request context goes into Agno's `session_state`. HiveGate fills it from the request: the user's name and profile (from `user_profile`), `timezone` and `locale`. If you send a `tenant_profile`, knowledge search is filtered to that tenant's documents, so one deployment can serve several customers without mixing their data.

## Streaming

`stream` defaults to `true`. The response is Server-Sent Events, one `event: message` per Agno event, each with a JSON `data` line:

```python
import json
import httpx

payload = {
    "message": "Summarize my open tickets.",
    "user_id": "user-1842",
    "session_id": "ticket-5521",
    "timezone": "UTC",
    "locale": "en",
}

with httpx.stream(
    "POST",
    "http://localhost:8000/v2/agents/support-agent/chat",
    headers={"X-API-Key": HIVEGATE_KEY},
    json=payload,
    timeout=120,
) as response:
    for line in response.iter_lines():
        if not line.startswith("data: "):
            continue
        event = json.loads(line[len("data: "):])
        if event.get("event") == "RunContent" and isinstance(event.get("content"), str):
            print(event["content"], end="", flush=True)
```

If a model call fails mid-stream, you get an `event: error` with a generic message. The details stay in the server log, so provider internals don't leak to clients.

## Picking the model per request

A request can set `model`. Otherwise HiveGate uses `DEFAULT_CHAT_MODEL`, and falls back to `gemini-3-flash-preview` if that's unset. Besides pinned IDs such as `claude-sonnet-4-6`, it accepts aliases like `anthropic:sonnet-latest` or `google:flash-latest`. An alias resolves to the vendor's newest model in that tier and never moves you up to a pricier tier. Model keys stay in the server's environment; clients never see them.

## API keys and cost per user

`/v2/*` requires an `X-API-Key`. Create keys with the admin secret:

```sh
curl -X POST http://localhost:8000/admin/api-keys \
  -H "X-Admin-Secret: $ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"name": "acme-web", "rate_limit": 1000}'
```

The raw key is in the `api_key` field of the response, and it's shown only once. For local work, `AUTH_DISABLED=true` skips the check. Never set it on a deployment other people can reach.

Every model call is metered: tokens, cache reads, tool calls, duration and USD cost go into a `token_usage` table, including failed and abandoned runs. To see which users cost the most:

```sh
curl -H "X-API-Key: $USAGE_KEY" \
  "http://localhost:8000/usage/summary?window=7d&group_by=user"
```

The usage endpoints accept a key with the `usage:read` scope. A key whose only scope is `usage:read` is refused on `/v2`, so a dashboard key can't call agents.

## Running it

Locally, Docker Compose starts Postgres and Qdrant and seeds demo agents:

```sh
git clone https://github.com/hivegate-ai/hivegate && cd hivegate
cp .env.example .env    # set GOOGLE_API_KEY, uncomment AUTH_DISABLED=true
docker compose up -d
./scripts/dev_setup.sh && source .venv/bin/activate && ./scripts/start_server.sh
```

For a server, use the prebuilt multi-arch image `ghcr.io/hivegate-ai/hivegate:latest`. The [deploy page](/deploy/) has one-click buttons for Render, Railway and Koyeb, plus Kubernetes and AWS, Azure and GCP manifests. The settings that matter:

| Variable | Why |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_DATABASE` | Postgres for agents, sessions, tokens and usage |
| `ADMIN_SECRET` | Protects `/admin/*`, where API keys are created |
| `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | At least one model provider |
| `SECRET_TOKEN_ENC_KEY` | Fernet key that encrypts stored user OAuth tokens |
| `QDRANT_URL` | Optional, for per-tenant knowledge |

`GET /health` is the health check. The deploy page ends with a five-step smoke test: health, list agents, create an agent, one real LLM call, then cleanup.

## What to know before scaling out

Conversation history is in Postgres, so any replica can serve the next turn. Two things live in process memory: the cached `Agent` objects, and runs that are paused waiting for a human to approve a tool call. A paused run has to be resumed on the process that paused it. If you use approvals, run one replica or route each session to the same instance. The [post on approvals](/blog/human-approval-agent-tool-calls/) covers that flow.

## When to use which

- Agents defined in code, one team, standard Agno features: **AgentOS**.
- Agents that act in each user's Gmail, Outlook or calendar; agents and prompts edited through an API; per-tenant knowledge; supervisor teams with container workers: **HiveGate**.

## Try it

- Deploy in one click from the [deploy page](/deploy/).
- Read the source, open an issue or star the repo on [GitHub](https://github.com/hivegate-ai/hivegate).
