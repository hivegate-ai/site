---
title: "From BizGenie to HiveGate: where our agent runtime began"
description: "HiveGate began as the agent backend for BizGenie, built on Agno's agent-api template. What carried over, with code, and where we use it now."
date: 2026-11-08
---

[HiveGate](https://github.com/hivegate-ai/hivegate) wasn't written from scratch. It started in May 2025 from [agent-api](https://github.com/agno-agi/agent-api), Agno's template for serving agents with FastAPI and Postgres. It became the agent backend for a product called BizGenie, and later we opened it up and gave it a new name.

This post covers where it came from, which parts are still the ones we built for BizGenie, and what we use it for now. The part with code is the approval flow: a tool marked `requires_confirmation`, a run that comes back `PAUSED`, and the commit call that resumes it. That flow dates from October 2025 and works the same way in HiveGate 0.3.1.

## What BizGenie asked of the backend

BizGenie was a B2B SaaS platform with two kinds of agents. Each employee got a personalized AI copilot, and there were shared, role-based experts on top.

That shape asks more of a backend than a single agent in a script does:

- A personal copilot works for one person. When it reads mail or books a meeting, it has to do that in that person's account, with that person's credentials.
- A shared expert is one agent with many users. Each conversation with it still belongs to one person, so sessions and history are per user.
- An agent that can send email on someone's behalf needs a stop before it sends.

None of this is about the model. Agno already gave us the agent itself: model calls, tools, memory and teams. The work was everything around it, which is what HiveGate is today.

## The timeline

- **May 2025:** the backend starts from Agno's agent-api template.
- **June 2025:** BizGenie's agents are added to it.
- **August 2025:** the `/v2` routes that HiveGate still serves.
- **October 2025:** the Google and Microsoft workspace toolkits (mail, calendar, contacts, drive) and `requires_confirmation` on the tools that write.
- **End of 2025:** open-source work begins.
- **September 2026:** the project is renamed HiveGate.
- **October 31, 2026:** 0.3.1, the first release on PyPI.

## What carried over: approval before a write

Letting an agent search an inbox is low risk. Letting it send an email or delete a message is not. Agno lets a toolkit name the tools that need a person's confirmation, and when the model calls one, Agno stops the run before the tool executes.

This is how HiveGate's email toolkit declares its writes, in `toolkits/email.py` (trimmed):

```python
Toolkit.__init__(
    self,
    name="EmailToolkit",
    tools=tools_list,
    requires_confirmation_tools=[
        "send_email",
        "create_draft",
        "send_draft",
        "trash_email",
        "delete_email_permanently",
        "modify_labels",
    ],
)
```

`search_emails` and `list_drafts` aren't on the list, so they run without a pause. The calendar, contacts and drive toolkits follow the same pattern, and so can your own:

```python
from agno.tools import Toolkit

class MyServiceToolkit(Toolkit):
    def __init__(self, user_id: str, service_name: str, auth: bool = True):
        super().__init__(
            name="my_service_toolkit",
            tools=[self.my_action if auth else self.auth_required],
            requires_confirmation_tools=["my_action"] if auth else [],
            stop_after_tool_call_tools=([] if auth else ["auth_required"]),
        )
        self.user_id = user_id
        self.service_name = service_name
```

### The run pauses

A chat request to an agent with the email toolkit:

```sh
curl -X POST http://localhost:8000/v2/agents/customer-support/chat \
  -H "X-API-Key: $HIVEGATE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Send Jane the password reset instructions.",
    "stream": false,
    "user_id": "user-42",
    "session_id": "sess-abc123",
    "timezone": "America/New_York",
    "locale": "en-US"
  }'
```

When the model decides to call `send_email`, the response isn't a finished answer. It has `status: "PAUSED"`, a `run_id`, and the proposed call with its arguments:

```json
{
  "content": null,
  "agent_id": "customer-support",
  "session_id": "sess-abc123",
  "status": "PAUSED",
  "run_id": "run-f47ac10b",
  "tools": [
    {
      "tool_call_id": "tc-001",
      "tool_name": "send_email",
      "requires_confirmation": true,
      "tool_args": {"to": "jane@acme.com", "subject": "Password Reset"},
      "result": null
    }
  ]
}
```

Nothing has been sent yet. Your app shows `tool_name` and `tool_args` to the user in whatever form fits: a confirmation card, an editable form, a message in Slack.

### Approve, edit or deny

The decision goes to `POST /v2/agents/{agent_id}/chat/commit` with the `run_id`, the same `user_id` and `session_id`, and one entry per pending tool in `updated_tools`. Here the reviewer changed the subject before approving:

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
      {
        "tool_call_id": "tc-001",
        "confirmed": true,
        "tool_args": {"to": "jane@acme.com", "subject": "Password Reset Instructions"},
        "confirmation_note": "Clearer subject"
      }
    ]
  }'
```

The run resumes, the email goes out through the user's own Gmail or Outlook account, and the response has the agent's final message. HiveGate copies only `confirmed`, `tool_args` (or `args`) and `confirmation_note` from each entry onto the paused call. Anything else is ignored.

Set `"confirmed": false` on every pending tool and the run doesn't resume at all. The response is `status: "cancelled"` with the content `"Tool execution cancelled by user."`, and no model call is made.

The same thing from a Python backend:

```python
import httpx

BASE = "http://localhost:8000/v2/agents/customer-support"
HEADERS = {"X-API-Key": HIVEGATE_KEY}

def commit(paused: dict, user_id: str, decisions: list[dict]) -> dict:
    body = {
        "run_id": paused["run_id"],
        "user_id": user_id,
        "session_id": paused["session_id"],
        "stream": False,
        "updated_tools": decisions,
    }
    response = httpx.post(f"{BASE}/chat/commit", headers=HEADERS, json=body, timeout=120)
    if response.status_code == 410:
        raise RuntimeError("The paused run is gone. Ask the agent again.")
    response.raise_for_status()
    return response.json()
```

### The limits that came with it

Two things about this flow are worth knowing before you rely on it:

- **Paused runs live in process memory.** If the process restarts, or the commit lands on another replica, commit returns 410 Gone ("Confirmation time window has elapsed"). Run a single replica, or route each session to the same instance, when you use approvals. The conversation itself is in Postgres, so the user keeps their history.
- **MCP tools have no approval gate yet.** Tools from an MCP server run without a pause. That's [#93](https://github.com/hivegate-ai/hivegate/issues/93) on the [roadmap](https://github.com/hivegate-ai/hivegate/issues/72).

HiveGate also records the API key that made the commit, not the person who clicked approve. If you need the reviewer's identity, store it in your own database before you call commit, or put it in `confirmation_note`, which is saved with the tool execution.

## What else carried over: each user's own accounts

The workspace toolkits from October 2025 are the other half of the copilot idea. An agent that books a meeting for a user does it in that user's Google or Microsoft calendar, not in a shared account.

Your app runs the OAuth consent and hands HiveGate the tokens:

```sh
curl -X POST http://localhost:8000/v2/users/user-42/tokens \
  -H "X-API-Key: $HIVEGATE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "integration_key": "google_calendar",
    "provider": "google",
    "token_type": "oauth2",
    "token_data": {
      "access_token": "ya29.a0...",
      "refresh_token": "1//0g...",
      "expires_in": 3599,
      "client_id": "1234-abc.apps.googleusercontent.com",
      "client_secret": "GOCSPX-..."
    }
  }'
```

HiveGate encrypts the token data with Fernet before it's written, refreshes the access token when a tool asks for it close to expiry, and gives it to the tool at the moment it runs. The model never sees it. The [per-user OAuth post](/blog/per-user-google-microsoft-oauth-ai-agents/) has the details.

## What HiveGate is now

Around that core, HiveGate today has agents, prompts and skills managed as data through the API, supervisor teams with Docker and Kubernetes workers (including Claude Code), per-tenant knowledge in Qdrant, a record of tokens and USD cost for every model call under `/usage`, Claude prompt caching, HTTP MCP servers in chat, OpenTelemetry and Sentry tracing, and one-click deploys to Railway, Render and Koyeb. It's MIT-licensed, and since 0.3.1 it installs from PyPI.

It's also no longer only ours. Six first-time contributors have joined since late September, with work that ranges from fixing the Qdrant healthcheck to working out how GitHub's and Atlassian's hosted MCP servers do OAuth.

## Where we use it today

We build our current AI projects on HiveGate:

- **A personal-finance app** whose agents propose and classify budgets.
- **[Joyful Chess](https://joyfulchess.com)**, a chess-learning project in the works. Its AI tutor is built on HiveGate.

That's our own use. It tells you what we test HiveGate against day to day. It isn't evidence that anyone else runs it, and we won't present it that way.

## When you don't need it

Agno's own [AgentOS](https://docs.agno.com/agent-os/introduction) also serves agents over HTTP, with sessions, human approval, RBAC and tracing. If your agents are defined in code and AgentOS covers what you need, use AgentOS.

HiveGate is for the case where agents and prompts are data you change over an API, each user connecting their own Google or Microsoft account, approvals that happen inside your product over REST, and a need to know what each user cost you.

## Try it

```sh
uv tool install hivegate-ai
mkdir my-agents && cd my-agents && hivegate init
# set GOOGLE_API_KEY in .env
docker compose up -d && hivegate serve
```

Then open `http://127.0.0.1:8000/docs`. The paused-run and commit endpoints are documented in the [agents API docs](/docs/api-agents/), and the toolkits and their confirmation lists in the [toolkits docs](/docs/toolkits/).

If this is useful, a star helps other people find the project: [⭐ github.com/hivegate-ai/hivegate](https://github.com/hivegate-ai/hivegate).
