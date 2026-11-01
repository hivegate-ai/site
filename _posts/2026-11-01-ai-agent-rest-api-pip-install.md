---
title: "AI agent REST API from pip install: HiveGate 0.3.1"
description: "HiveGate 0.3.1 is on PyPI. Install it, start Postgres and Qdrant, and serve Agno agents over a REST API with sessions, approvals and cost metering."
date: 2026-11-01
---

Until last week, trying [HiveGate](https://github.com/hivegate-ai/hivegate) meant cloning the repo, copying `.env.example`, running a setup script and starting the server from the checkout. That's fine if you want to work on HiveGate. It's a lot to ask if you only want to see whether it fits your agents.

HiveGate 0.3.1, released on October 31, is the first release on PyPI. You install it as a tool, write a starter config with one command, start Postgres and Qdrant, and serve. This post walks through that path from an empty directory to an AI agent REST API with per-user sessions, a paused tool call you approve over HTTP, and a cost record for every model call. It ends with what changes when you take it off your laptop.

HiveGate is an MIT-licensed FastAPI service built on [Agno](https://github.com/agno-agi/agno). You write the agent. HiveGate serves it. It is not a request-routing API gateway like Kong.

## What you need

- Python 3.11 or newer, and [uv](https://docs.astral.sh/uv/) or [pipx](https://pipx.pypa.io/)
- Docker, for Postgres and Qdrant
- An API key for a model provider. The seeded demo agents use Gemini, so `GOOGLE_API_KEY` is the shortest path. OpenAI, Anthropic, xAI, Z.ai and DeepSeek keys also work.

## Install

```sh
uv tool install hivegate-ai   # or: pipx install hivegate-ai
```

The package is `hivegate-ai` because PyPI refused `hivegate` as too similar to an existing project. The command is still `hivegate`.

Install it as a tool rather than into a project's virtual environment. The package's top-level modules have generic names (`api`, `agents`, `db`), and they can clash with other libraries in a shared environment. `uv tool` and `pipx` give it an environment of its own.

## Write the config

```sh
mkdir my-agents && cd my-agents
hivegate init
```

`init` writes four files: `compose.yaml`, `.env`, `db/migrations/setup.sql` and `sql/sample_data.sql`. The `.env` is not a copy of the example file. Three values are filled in for a first local run:

- `AUTH_DISABLED=true`, so you can call `/v2` without an API key while the server only listens on your machine.
- `ADMIN_SECRET`, set to a random 32-byte value instead of the placeholder.
- `SECRET_TOKEN_ENC_KEY`, a fresh Fernet key. HiveGate encrypts the per-user OAuth tokens it stores with this key, so keep it with your data.

Running `init` again refuses to overwrite anything. With `--force` it rewrites the compose files but still keeps an existing `.env`, because that file holds your API keys and the key your stored tokens are encrypted with.

Open `.env` and set your model key:

```sh
GOOGLE_API_KEY=...
```

## Start the stack

```sh
docker compose up -d   # Postgres + Qdrant, seeds demo agents
hivegate serve         # http://127.0.0.1:8000/docs
```

Compose starts Postgres and Qdrant, creates the schema and seeds a handful of demo agents and teams. Since 0.3.1 it publishes their ports on `127.0.0.1` only, so the databases aren't reachable from your network by accident.

`hivegate serve` loads `.env` from the current directory and starts the API on `127.0.0.1:8000`. If no model key is set, it starts anyway and prints a warning, because agents can't answer without one. The interactive OpenAPI docs are at `/docs`.

## First calls

Check that it's up, then list the agents:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/v2/agents
```

You'll see the seeded agents, including `demo-assistant`. Chat with it:

```bash
curl -X POST http://localhost:8000/v2/agents/demo-assistant/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the capital of France?",
    "stream": false,
    "user_id": "user-1",
    "session_id": "session-1",
    "timezone": "UTC",
    "locale": "en-US"
  }'
```

The response carries the answer and the identifiers you'll use later:

```json
{
  "content": "The capital of France is Paris.",
  "agent_id": "demo-assistant",
  "session_id": "session-1",
  "model": "gemini-3-flash-preview",
  "status": "completed",
  "run_id": "run-f47ac10b",
  "tools": []
}
```

Leave out `"stream": false` and you get server-sent events instead, which is what a chat UI wants.

Every chat names a `user_id` and a `session_id`. Send another message with the same pair and the agent sees the earlier turns, because history lives in Postgres, not in the process. Use a different `user_id` and that user gets their own sessions and memory. Nothing in your agent code has to track who is who.

## Agents are data

The demo agents came from SQL, but you create your own over the same API. An agent is an id, a name and a prompt template, plus optional settings for memory, history and reasoning:

```bash
curl -X POST http://localhost:8000/v2/agents \
  -H "Content-Type: application/json" \
  -d '{
    "id": "my-first-agent",
    "name": "My First Agent",
    "template": "You are a helpful assistant that answers questions concisely.",
    "description": "A simple Q&A agent",
    "tags": ["qa", "general"]
  }'
```

It's available at `/v2/agents/my-first-agent/chat` straight away, with no redeploy. Changing a prompt is an API call, not a release. The [agents API docs](/docs/api-agents/) list every field.

## A tool call that waits for a person

Letting an agent search an inbox is low risk. Letting it send an email is not. HiveGate's built-in Google and Microsoft toolkits mark every write as `requires_confirmation`: `send_email`, `trash_email`, `schedule_meeting` and the rest. Your own Agno toolkits opt in with `requires_confirmation_tools=[...]`.

When the model calls one of those tools, the run stops before the tool executes, and the chat response says so:

```json
{
  "content": null,
  "status": "PAUSED",
  "run_id": "run-f47ac10b",
  "tools": [
    {
      "tool_call_id": "tc-001",
      "tool_name": "send_email",
      "requires_confirmation": true,
      "tool_args": {"to": "jane@acme.com", "subject": "Password Reset"}
    }
  ]
}
```

Nothing has been sent yet. Show the pending call wherever your users are, then send the decision back. The reviewer can edit the arguments, not only say yes or no:

```bash
curl -X POST http://localhost:8000/v2/agents/my-first-agent/chat/commit \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "run-f47ac10b",
    "stream": false,
    "user_id": "user-1",
    "session_id": "session-1",
    "updated_tools": [
      {
        "tool_call_id": "tc-001",
        "confirmed": true,
        "tool_args": {"to": "jane@acme.com", "subject": "Password Reset Instructions"}
      }
    ]
  }'
```

Set `"confirmed": false` and the run ends with `status: "cancelled"` without calling the tool. Since 0.3.1 the same works for team runs, which used to pause and then couldn't be committed (#116).

Two limits to know. Paused runs live in the server's memory, so a restart or a request that lands on another replica gets `410 Gone`. Run a single replica, or route each session to the same instance, when you use approvals. And tools from MCP servers don't have an approval gate yet; that's [roadmap item #72](https://github.com/hivegate-ai/hivegate/issues/72). The [human approval post](/blog/human-approval-agent-tool-calls/) covers the flow in depth.

## What did that cost?

Every model call is metered: input, output, cache-read and cache-write tokens, and the USD cost from a versioned price table. The read-only `/usage` API groups it by agent, user, tenant, model, API key or status:

```bash
curl "http://localhost:8000/usage/summary?window=24h&group_by=user"
curl "http://localhost:8000/usage/calls?order=cost&limit=10"
```

`/usage/calls` returns the most expensive calls first, with session and run ids, so you can find the conversation behind a spike. With a Claude model, prompt caching is on by default in 0.3.1, and the cache-read tokens show up in the same records. The [token cost post](/blog/llm-token-usage-cost-tracking/) shows the queries behind a per-user cost report.

## Off your laptop

`AUTH_DISABLED=true` is only acceptable while nothing else can reach the server, and `hivegate serve` enforces that. Ask it to listen on another host with auth off and it refuses:

```sh
$ hivegate serve --host 0.0.0.0
Refusing to serve on 0.0.0.0 with AUTH_DISABLED on: every route would be open. Remove it from .env.
```

It refuses the placeholder `ADMIN_SECRET` the same way. Remove `AUTH_DISABLED` from `.env`, restart, and create an API key with the admin secret `init` generated:

```bash
curl -X POST http://localhost:8000/admin/api-keys \
  -H "X-Admin-Secret: $ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"name": "Frontend", "owner_id": "team-frontend", "scopes": ["agents:read", "agents:chat"]}'
```

The raw key (`agk_...`) is returned once and stored as a SHA-256 hash. Send it as `X-API-Key` on every `/v2` call. For the cost dashboard, a key with only the `usage:read` scope can read `/usage` and nothing else. The [authentication docs](/docs/authentication/) have the details.

For a hosted deployment you don't need the package at all. The prebuilt image deploys in one click to Railway, Render or Koyeb from the [deploy page](/deploy/), and the [deployment docs](/docs/deployment/) cover a production setup of your own.

## Upgrading

```sh
uv tool upgrade hivegate-ai
hivegate migrate
```

`migrate` reads `.env` from the current directory and applies any database changes the new version ships. Coming from a clone of 0.3.0, apply `db/migrations/011_token_usage_cost.sql` (it adds the metering columns), and note that `compose.yaml` now reads `DB_PASS` and `DB_DATABASE` instead of `DB_PASSWORD` and `DB_NAME`.

## What else is in 0.3.1

Everything merged since 0.3.0 on September 29:

- Per-call token cost metering and the `/usage` API (#109)
- Prompt caching for Claude models (#110)
- Approvable paused team runs (#116)
- `error_code: "provider_billing"` and a plain message when a provider account is out of credits, instead of the provider's raw error (#125)
- A warning that names the server when an MCP server with an unsupported transport is dropped, instead of the agent silently getting fewer tools (#146, from first-time contributor @coughlmao)
- Dependency upgrades that clear the open security advisories (#134)

The full list is in the [changelog](https://github.com/hivegate-ai/hivegate/blob/main/CHANGELOG.md).

## When you don't need HiveGate

Agno ships its own [AgentOS](https://docs.agno.com/agent-os/introduction), which serves agents defined in code over HTTP with sessions, human approval, RBAC and tracing. If your agents live in your codebase and AgentOS covers what you need, use AgentOS. It's maintained by the Agno team and tracks Agno releases.

HiveGate is for the case where agents and prompts are data you change over an API, each of your users connects their own Google or Microsoft account, approvals happen in your product over REST, and you need to know what each user cost you.

## Try it

```sh
uv tool install hivegate-ai
mkdir my-agents && cd my-agents && hivegate init
# set GOOGLE_API_KEY in .env
docker compose up -d && hivegate serve
```

Then open `http://127.0.0.1:8000/docs`. The [quickstart](/docs/quickstart/) and the rest of the [docs](/docs/) go from there, and issues and questions are welcome on [GitHub](https://github.com/hivegate-ai/hivegate).

If this is useful, a star helps other people find the project: [⭐ github.com/hivegate-ai/hivegate](https://github.com/hivegate-ai/hivegate).
