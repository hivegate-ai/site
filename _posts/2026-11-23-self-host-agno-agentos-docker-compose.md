---
title: "Self-host Agno AgentOS or HiveGate with Docker Compose"
description: "What self-hosting Agno agents takes with AgentOS or HiveGate: the Compose services, Postgres but no Redis, auth, and resuming a paused run by run_id."
date: 2026-11-23
---

You have an [Agno](https://github.com/agno-agi/agno) agent that works, and you want it running on your own machine or server, behind an HTTP API, with its data in your own database. The first questions are practical. Which containers? Does it need Redis? What about auth? And when an agent pauses for a human to approve a tool call, how does your app answer that run over REST?

This post compares the two self-hosted options built on Agno: Agno's own **AgentOS**, from its `agentos-docker` template, and **[HiveGate](https://github.com/hivegate-ai/hivegate)**, the MIT-licensed FastAPI service we maintain. HiveGate serves Agno agents over a REST API. It is not a request-routing API gateway like Kong.

The short answer first. Both need Postgres. Neither needs Redis. AgentOS runs as two containers: Postgres and the API. HiveGate runs as Postgres, the API and, if you want per-tenant knowledge, Qdrant.

## Which one you need

Start with AgentOS if your agents are defined in Python in your own repo, one team runs them, and you want Agno's newest features as soon as they ship. It's maintained by the Agno team, and the template comes with a UI at os.agno.com, an MCP endpoint for Claude and ChatGPT, scheduling and human approvals.

HiveGate is for a narrower case: agents that act *for your users* in their own Google or Microsoft accounts. Each user's OAuth tokens are stored, encrypted and refreshed on the server. Agents, prompts and skills are records you change through the API, not code you redeploy. Every model call is metered per user. If you don't need those, AgentOS is the simpler choice.

## AgentOS with Docker Compose

The [agentos-docker](https://github.com/agno-agi/agentos-docker) template has two services in `compose.yaml`:

| Service | Image | What it holds |
|---|---|---|
| `agentos-db` | `agnohq/pgvector:18` | Sessions, memory, knowledge vectors, runs |
| `agentos-api` | built from the repo's `Dockerfile` | The FastAPI app (`app.main:app`) on port 8000 |

There's no Redis and no separate worker service. To run it locally:

```sh
git clone https://github.com/agno-agi/agentos-docker agent-platform
cd agent-platform
cp example.env .env        # set OPENAI_API_KEY
docker compose up -d --build
```

The API docs are then at `http://localhost:8000/docs`. The dev compose file mounts the repo into the container and runs uvicorn with `--reload`, so you edit agents in `agents/` and register them in `app/main.py`.

Two details in the dev compose file are worth knowing before you put it on a server. It mounts `/var/run/docker.sock` into the API container, because the template's coding agents can use Docker sandboxes. And both ports bind to `127.0.0.1`, so nothing is exposed until you add a reverse proxy.

For production, the template has an override file:

```sh
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

The override turns on token checks and runs the code built into the image. Auth is JWT: you connect your instance at os.agno.com, enable token-based authorization, and put the public verification key in `.env` as `JWT_VERIFICATION_KEY`. The template refuses to serve production traffic without it (or a `JWT_JWKS_FILE`). You also set `AGENTOS_URL` to your public HTTPS URL and a strong `DB_PASS`. The README is explicit about scaling: keep one API container.

## HiveGate with Docker Compose

HiveGate's repo ships a `compose.yaml` for its data services. `hivegate init` writes the same file into an empty directory if you installed from PyPI instead of cloning:

```yaml
services:
  pgvector:
    image: agnohq/pgvector:16
    restart: unless-stopped
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/migrations/setup.sql:/docker-entrypoint-initdb.d/01-setup.sql:ro
      - ./sql/sample_data.sql:/docker-entrypoint-initdb.d/02-sample-data.sql:ro
    environment:
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASS:-postgres}
      POSTGRES_DB: ${DB_DATABASE:-postgres}
    # ...healthcheck: pg_isready

  qdrant:
    image: qdrant/qdrant:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:6333:6333"
      - "127.0.0.1:6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
```

On the first start, Postgres runs `setup.sql` (tables for agents, prompts, user tokens and usage) and seeds the demo agents. Agno creates its own session tables in the `ai` schema at runtime. Qdrant is only for knowledge search; leave `QDRANT_URL` empty and HiveGate runs without it.

That file runs the API on your host with `hivegate serve`. To run the API in Compose as well, clone a release tag and add a `compose.override.yaml` next to `compose.yaml`. Compose merges the two files automatically:

```yaml
# compose.override.yaml
services:
  hivegate:
    build: .
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    env_file: .env
    environment:
      PORT: "8000"
      DB_HOST: pgvector        # .env says 127.0.0.1, which is right only on the host
      DB_PORT: "5432"
      QDRANT_URL: http://qdrant
    depends_on:
      pgvector:
        condition: service_healthy
    networks:
      - hivegate
```

Then:

```sh
git clone --branch v0.4.1 https://github.com/hivegate-ai/hivegate && cd hivegate
cp .env.example .env
# set GOOGLE_API_KEY (the demo agents use Gemini), ADMIN_SECRET, and
# SECRET_TOKEN_ENC_KEY, the Fernet key that encrypts stored user tokens
# (this needs the cryptography package on the host):
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
docker compose up -d --build
curl http://localhost:8000/health
```

`/health` answers `{"status": "success"}` once the database is reachable. The image starts `uvicorn api.main:app` on `PORT`.

`setup.sql` runs only when the Postgres volume is empty. After an upgrade, apply the new migrations with the CLI that ships in the image:

```sh
docker compose run --rm hivegate python -m hivegate_cli migrate
```

It records what it applied in a `hivegate_migrations` table, so running it twice is safe.

Auth is API keys rather than JWT. `ADMIN_SECRET` protects `/admin/*`, where you create keys for your apps:

```sh
curl -X POST http://localhost:8000/admin/api-keys \
  -H "X-Admin-Secret: $ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"name": "web-app", "rate_limit": 1000}'
```

The raw key comes back once, in `api_key`. Every `/v2` call sends it as `X-API-Key`. Your own backend authenticates the end user and passes their `user_id` in each request, which is what HiveGate uses to pick that user's session, memory, OAuth tokens and usage rows.

For a server, put a reverse proxy with TLS in front of port 8000 and use a managed or backed-up Postgres. The [deploy page](/deploy/) has one-click Render, Railway and Koyeb deploys and Kubernetes manifests if you'd rather not run Compose.

## Side by side

| | AgentOS (`agentos-docker`) | HiveGate |
|---|---|---|
| Containers | Postgres, API | Postgres, API, Qdrant (optional) |
| Redis | No | No |
| Agents defined in | Python files in the repo | Records created through `/v2/agents` |
| API auth | JWT, key from os.agno.com | `X-API-Key`, keys created with `ADMIN_SECRET` |
| End users' OAuth tokens | Not built in | Stored per user, encrypted, refreshed on read |
| Paused runs | Persisted in the database | In process memory |
| API replicas | One | One, or sticky sessions, if you use approvals |

## Approving or declining a paused run by `run_id`

When a tool marked for confirmation is called, both runtimes pause the run and give you a `run_id`. Your app shows the proposed call to a person and sends the decision back.

In AgentOS, you continue the run with a form POST. `tools` is a JSON string of the tool executions with your decision in them:

```sh
curl -X POST http://localhost:8000/agents/support-agent/runs/$RUN_ID/continue \
  -H "Authorization: Bearer $JWT" \
  -F session_id=ticket-5521 \
  -F stream=false \
  -F 'tools=[{"tool_call_id": "tc-001", "tool_name": "send_email", "tool_args": {"to": "jane@acme.com"}, "confirmed": true}]'
```

AgentOS loads the paused run from the database, so the decision still works after a restart.

In HiveGate, the run comes back from `/chat` with `status: "PAUSED"` and the pending calls in `tools`. You answer it with a JSON commit:

```sh
curl -X POST http://localhost:8000/v2/agents/customer-support/chat/commit \
  -H "X-API-Key: $HIVEGATE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "run-f47ac10b",
    "stream": false,
    "user_id": "user-42",
    "session_id": "sess-abc123",
    "updated_tools": [
      {"tool_call_id": "tc-001", "confirmed": false,
       "confirmation_note": "Not to customers on a Sunday."}
    ]
  }'
```

`confirmed: true` runs the call, with any `tool_args` you edited. `confirmed: false` declines it. The [agents API docs](/docs/api-agents/) have the full request and response.

The limit to plan around: HiveGate keeps paused runs in process memory. After a restart, or on another replica, the commit returns `410 Gone`. Run one replica when you use approvals, or route each session to the same instance.

### When the person declines everything

In v0.4.1, a commit that declines every call ends the run with `status: "cancelled"`. The model is never told, so it never answers the user. Declining some of the calls already resumed the run.

@rajshadow changed that in [#254](https://github.com/hivegate-ai/hivegate/pull/254), merged for the next release. A run whose calls are all declined now resumes like any other commit: the declined calls don't run, Agno passes them to the model as rejected along with your `confirmation_note`, and the commit returns the model's reply. "No" is an answer the agent should hear. Two consequences for clients: a declined commit now calls the model, so it shows up in `/usage`, and a client that checked for `cancelled` will now get a completed run. A run that's no longer in memory still gets `cancelled` rather than a 410.

## Before you pick

- Agents in code, one team, Agno's UI and MCP endpoint, approvals that survive restarts: **AgentOS**.
- Agents acting in each user's Gmail, Outlook or calendar, agents and prompts managed through an API, cost per user and per tenant: **HiveGate**.

Both are Docker Compose and Postgres on your own box, so trying each one costs an afternoon, not a migration.

## Try it

- The compose stack and API docs: [hivegate.dev/docs](/docs/).
- One-click deploys: [hivegate.dev/deploy](/deploy/).
- If this helped, star the repo: ⭐ [github.com/hivegate-ai/hivegate](https://github.com/hivegate-ai/hivegate)
