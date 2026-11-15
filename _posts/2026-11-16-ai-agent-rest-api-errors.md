---
title: "AI agent REST API errors: what HiveGate 0.4.0 changes"
description: "HiveGate 0.4.0 returns 502 when a model call fails and 400 for an MCP setup chat can't run, instead of a 200 that looks like an answer."
date: 2026-11-16
---

An agent API can fail in a way that is worse than going down: it answers. The provider rejects the key, the account is out of credits, or the model is unavailable, and the API still returns `200 OK` with the provider's error text where the answer should be. A chat UI shows it to the user as if the agent said it. An eval scores it. A retry loop sees success and stops retrying. A cost report counts it as a completed conversation.

Until last week, [HiveGate](https://github.com/hivegate-ai/hivegate) did that. HiveGate 0.4.0, released on November 11, fixes it, along with two related failures that also looked like success. This post covers what changed, what your client needs to do about it, and how to check that a failure is reported as one.

HiveGate is an MIT-licensed FastAPI service built on [Agno](https://github.com/agno-agi/agno) that serves AI agents over a REST API. You write the agent. HiveGate serves it. It is not a request-routing API gateway like Kong.

## Three failures that looked like success

All three fixes in 0.4.0 came from outside contributors, and all three have the same shape: the API said one thing and did another.

- **A failed model call returned 200** with the provider's error as the answer. Now it returns `502` (#205, by @rajshadow).
- **A chat agent with an MCP server chat can't use** (`stdio` or `sse`) ran without that server's tools and said nothing. Now the request is refused with `400` (#206, by @rayulumukku).
- **`POST /v2/agents/{agent_id}/session/clear` returned success and deleted nothing.** Now it deletes the session's history (#161, by @rajshadow).

The first two are breaking changes for any client that depended on the old behavior, so they're under "Upgrading" in the [release notes](https://github.com/hivegate-ai/hivegate/releases/tag/v0.4.0).

## Failed model calls return 502

Agno doesn't always raise when a provider call fails. In many cases it returns a run output with an error status and the provider's message as its content. HiveGate used to pass that through as a normal chat response. In 0.4.0, a non-streaming chat or team run whose model call fails returns HTTP 502 with a body your code can branch on.

To see it, set a wrong key in `.env` (for example `GOOGLE_API_KEY=wrong`), restart `hivegate serve`, and call one of the demo agents:

```bash
curl -i -X POST http://localhost:8000/v2/agents/demo-assistant/chat \
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

```
HTTP/1.1 502 Bad Gateway
content-type: application/json

{
  "status": "error",
  "error": "Model provider failed for gemini-3-flash-preview; check GOOGLE_API_KEY, provider credits, and model availability.",
  "detail": "Model provider failed for gemini-3-flash-preview; check GOOGLE_API_KEY, provider credits, and model availability.",
  "error_code": "model_provider_error"
}
```

The message names the environment variable for the model's provider: `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `XAI_API_KEY`, `ZAI_API_KEY` or `DEEPSEEK_API_KEY`. It does not include the provider's raw exception, which can carry request ids, account details or a fragment of the key.

`error_code` is the field to branch on. The message is for people and may change. There are three codes:

| `error_code` | When | What to do |
|---|---|---|
| `model_provider_error` | Bad key, provider outage, model not available | Check the key named in `detail`; retry later on an outage |
| `provider_billing` | The provider account is out of credits (or the provider returned 402) | Tell whoever owns the provider account; retrying won't help |
| `model_refusal_error` | The model declined the request (`stop_reason=refusal`) | Change the request; the same request will be declined again |

`provider_billing` dates from 0.3.1 (#125), which replaced the provider's raw billing error with a plain message. The difference in 0.4.0 is that it now arrives with a 502 instead of inside a 200.

Why 502 and not 500? The request was valid and HiveGate worked. The upstream it depends on, the model provider, failed. That is what 502 Bad Gateway means, and it lets a load balancer, a client library or an alert rule tell "the provider failed" apart from "HiveGate crashed".

## Streaming ends with an `error` event

A streaming response has already sent `200 OK` and its headers by the time the model fails, so the status code can't change. In 0.4.0 the stream ends with an SSE event named `error` instead:

```
event: error
data: {"event": "RunError", "run_id": "run-f47ac10b", "session_id": "session-1", "agent_id": "demo-assistant", "status": "error", "error": "Model provider failed for gemini-3-flash-preview; check GOOGLE_API_KEY, provider credits, and model availability.", "detail": "Model provider failed for gemini-3-flash-preview; check GOOGLE_API_KEY, provider credits, and model availability.", "error_code": "model_provider_error", "content": "Model provider failed for gemini-3-flash-preview; check GOOGLE_API_KEY, provider credits, and model availability."}
```

It carries the same `status`, `error`, `detail` and `error_code` as the 502 body, plus the run identifiers when the run had started. `content` holds the safe message too, so an existing chat client that renders `content` shows something sensible before you update it.

Team runs need one more detail. When one member of a team fails, the event is cleaned up the same way but sent as a normal `message` event, and the team keeps going: the supervisor may recover with another member. The stream only ends with `error` when the team run itself fails.

## What your client needs to change

If your client already treats non-2xx responses as errors, the non-streaming change mostly works for you. What breaks is code that read the error text out of a 200 reply, for example to show "check your API key" in an admin screen. Read `error_code` from the 502 body instead.

A minimal non-streaming client in Python:

```python
import httpx

BASE = "http://localhost:8000"
HEADERS = {"X-API-Key": "agk_..."}

def chat(agent_id: str, message: str, user_id: str, session_id: str) -> str:
    r = httpx.post(
        f"{BASE}/v2/agents/{agent_id}/chat",
        headers=HEADERS,
        json={
            "message": message,
            "stream": False,
            "user_id": user_id,
            "session_id": session_id,
            "timezone": "UTC",
            "locale": "en-US",
        },
        timeout=120,
    )
    if r.status_code == 502:
        err = r.json()
        if err["error_code"] == "provider_billing":
            raise RuntimeError("provider out of credits: " + err["detail"])
        raise RuntimeError(f"{err['error_code']}: {err['detail']}")
    r.raise_for_status()
    return r.json()["content"]
```

For streaming, watch the event name, not only the data:

```python
import json
import httpx

def stream_chat(agent_id: str, payload: dict):
    event = "message"
    with httpx.stream("POST", f"{BASE}/v2/agents/{agent_id}/chat",
                      headers=HEADERS, json=payload, timeout=None) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = json.loads(line.split(":", 1)[1])
                if event == "error":
                    raise RuntimeError(f"{data['error_code']}: {data['detail']}")
                if isinstance(data.get("content"), str):
                    yield data["content"]
```

If you retry on errors, retry `model_provider_error` with backoff and leave the other two alone. Retrying a refusal or an empty provider account costs time and, for refusals, tokens.

## Failed calls in the cost records

Every model call HiveGate makes is metered, including failed ones. A failed run is recorded with `status: "error"` and the error text, so a cost report doesn't count it as a completed conversation. To list recent failures, with their session and run ids:

```bash
curl "http://localhost:8000/usage/calls?status=error&limit=20" \
  -H "X-API-Key: $USAGE_KEY"
```

Or see the last day's totals split by status:

```bash
curl "http://localhost:8000/usage/summary?window=24h&group_by=status" \
  -H "X-API-Key: $USAGE_KEY"
```

A key with only the `usage:read` scope can read these and nothing else. Before 0.4.0 the record already said `error`, but the client had been told the call succeeded, so the two disagreed. Now they match. The [token cost post](/blog/llm-token-usage-cost-tracking/) covers the rest of the `/usage` API.

## MCP servers chat can't use are refused

An agent's `worker_config.mcp_servers` can list MCP servers. Chat requests connect to HTTP servers (`type: "http"` or `"streamable-http"`) and give the agent their tools. `stdio` servers are only for supervisor workers, which run in containers. Before 0.4.0, a chat agent configured with a `stdio` or `sse` server ran without those tools. It answered, and it couldn't do the thing the tools were for. 0.3.1 added a log warning (#146). 0.4.0 refuses the request.

One case to watch: a server entry with no `type` counts as `stdio`. This config:

```json
"worker_config": {
  "mcp_servers": [
    {"name": "budget", "url": "https://mcp.example.com/mcp"}
  ]
}
```

now gets this, for streaming and non-streaming chat alike, before the model is called:

```json
{
  "detail": "Unsupported MCP transport 'stdio' for server 'budget'. Supported transports for chat agents are: 'http', 'streamable-http'."
}
```

Add `"type": "http"` and it works. A missing URL, a relative one or a non-HTTP scheme such as `ftp://` is refused the same way, with a message that names the server. Supervisor and worker agents keep `stdio`. The [agents API docs](/docs/api-agents/) describe MCP tools in chat.

A 400 is the right failure here because the configuration is wrong and every request will fail the same way. You find out on the first request, in testing, instead of from a user asking why the agent "can't see" their data.

## Session clear deletes

`POST /v2/agents/{agent_id}/session/clear` returned success and left the history in place. In 0.4.0 it deletes from the same storage chat reads. Pass a `session_id` to clear one session, or a `user_id` alone to clear that user's sessions for this agent:

```bash
curl -X POST http://localhost:8000/v2/agents/demo-assistant/session/clear \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-1", "session_id": "session-1"}'
```

With neither, it returns 400. If nothing matches, it returns 404 rather than a success that deleted nothing. It clears conversation history only; the user's memories, stored OAuth tokens and knowledge stay. If you offered users a "clear conversation" button on 0.3.x, their history was not cleared. Upgrading fixes it from now on.

## Upgrading

```sh
uv tool upgrade hivegate-ai
hivegate serve
```

0.4.0 has no database changes. The release also documents `DOCS_ENABLED`, `CORS_ORIGIN_LIST` and the Bright Data settings, and fixes `docker compose up --wait`, which used to fail on the Qdrant healthcheck (#154, by @Arun100203). The full list is in the [changelog](https://github.com/hivegate-ai/hivegate/blob/main/CHANGELOG.md).

## What's still open

Two limits from earlier releases still apply. MCP tools don't have an approval gate yet ([#72](https://github.com/hivegate-ai/hivegate/issues/72)), so a write through an MCP server runs without pausing. And paused runs live in the server's memory, so a restart or another replica returns `410 Gone` on commit. The [human approval post](/blog/human-approval-agent-tool-calls/) covers both.

If you want to help, the [good first issues](https://github.com/hivegate-ai/hivegate/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) include 15 short write-ups of how hosted MCP servers (Linear, Sentry, Stripe, Supabase and others) do OAuth.

## When you don't need HiveGate

If your agents are defined in code and Agno's [AgentOS](https://docs.agno.com/agent-os/introduction) covers what you need, use AgentOS. It's maintained by the Agno team and tracks Agno releases. HiveGate is for the case where agents and prompts are data you change over an API, each user connects their own Google or Microsoft account, approvals happen in your product over REST, and you need to know what each user cost you.

## Try it

```sh
uv tool install hivegate-ai
mkdir my-agents && cd my-agents && hivegate init
# set GOOGLE_API_KEY in .env
docker compose up -d && hivegate serve
```

Then open `http://127.0.0.1:8000/docs`. The [quickstart](/docs/quickstart/) goes from there.

If this is useful, a star helps other people find the project: [⭐ github.com/hivegate-ai/hivegate](https://github.com/hivegate-ai/hivegate).
