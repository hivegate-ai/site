---
title: "Human approval before risky agent tool calls"
description: "Pause an AI agent before it sends an email or deletes data, let a person approve, edit or deny the call over a REST API, and keep a record of the decision."
date: 2026-10-12
---

Letting an agent search an inbox is low risk. Letting it send an email, cancel a meeting or permanently delete a message is not. A wrong recipient or a hallucinated date becomes a real-world mistake. The usual answer is human-in-the-loop: the agent proposes the call, a person reviews it, and only then does it run.

This post shows how that works in [HiveGate](https://github.com/hivegate-ai/hivegate), an open-source FastAPI service for [Agno](https://github.com/agno-agi/agno) agents. The run pauses, your app gets the proposed call, and a second request approves, edits or denies it.

## Which tools pause

Agno lets a toolkit mark tools as `requires_confirmation`. When the model calls one, Agno stops the run before executing it. HiveGate's built-in toolkits mark every write:

- **Email:** `send_email`, `create_draft`, `send_draft`, `trash_email`, `delete_email_permanently`, `modify_labels`
- **Calendar:** `schedule_meeting`, `schedule_meeting_find_time`, `cancel_meeting`
- **Contacts:** `create_contact`, `update_contact`, `delete_contact`
- **Drive:** `read_file`
- **Workers:** `run_claude_code`, `run_managed_agent`

Read-only tools such as `search_emails` and `list_events` run without a pause. Your own Agno toolkits opt in the same way, through `requires_confirmation_tools=[...]`. Tools from MCP servers don't have an approval gate yet. That's on the [roadmap](https://github.com/hivegate-ai/hivegate/issues/72).

## Step 1: the run pauses

A normal chat request:

```sh
curl -X POST http://localhost:8000/v2/agents/support-agent/chat \
  -H "X-API-Key: $HIVEGATE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Email jordan@acme.example that the renewal call moves to Thursday 3pm.",
    "user_id": "user-1842",
    "session_id": "inbox-1",
    "timezone": "America/Chicago",
    "locale": "en-US",
    "stream": false,
    "user_profile": {
      "profile_id": "user-1842",
      "email": "dana@acme.example",
      "full_name": "Dana Lee",
      "role": "Account manager",
      "tenant_id": "acme"
    }
  }'
```

Instead of a finished answer, the response has `status: "PAUSED"`, a `run_id`, and the pending call with its arguments (trimmed here):

```json
{
  "agent_id": "support-agent",
  "session_id": "inbox-1",
  "status": "PAUSED",
  "run_id": "6f1c9a2e-...",
  "tools": [
    {
      "tool_call_id": "call_8Jx2...",
      "tool_name": "send_email",
      "requires_confirmation": true,
      "tool_args": {
        "to": ["jordan@acme.example"],
        "subject": "Renewal call moved to Thursday",
        "body_text": "Hi Jordan, the renewal call is now Thursday at 3pm CT. Thanks, Dana"
      },
      "result": null
    }
  ]
}
```

Nothing has been sent yet. With `"stream": true`, you get the same data as an SSE event whose `event` field is `RunPaused`, and then the stream ends.

Show `tool_name` and `tool_args` to the user, or to whoever reviews actions for them, in whatever form fits your app: a confirmation card, an editable form, a Slack message.

## Step 2: approve, edit or deny

The decision goes to `POST /v2/agents/{agent_id}/chat/commit` with the `run_id`, the same `user_id` and `session_id`, and one entry per pending tool in `updated_tools`.

**Approve as proposed:**

```sh
curl -X POST http://localhost:8000/v2/agents/support-agent/chat/commit \
  -H "X-API-Key: $HIVEGATE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "6f1c9a2e-...",
    "user_id": "user-1842",
    "session_id": "inbox-1",
    "stream": false,
    "updated_tools": [
      {"tool_call_id": "call_8Jx2...", "confirmed": true}
    ]
  }'
```

The agent resumes, the email is sent through the user's own Gmail or Outlook account, and the response has the agent's final message, `status: "completed"` and the token usage for the resumed part.

**Edit, then approve.** The reviewer fixed the time, so send the corrected arguments with the approval. `tool_args` replaces the proposed arguments, so send the full set:

```json
{"tool_call_id": "call_8Jx2...", "confirmed": true,
 "tool_args": {
   "to": ["jordan@acme.example"],
   "subject": "Renewal call moved to Thursday",
   "body_text": "Hi Jordan, the renewal call is now Thursday at 4pm CT. Thanks, Dana"
 },
 "confirmation_note": "Corrected time to 4pm"}
```

**Deny:**

```json
{"tool_call_id": "call_8Jx2...", "confirmed": false, "confirmation_note": "Wrong recipient"}
```

If every pending tool is denied, HiveGate doesn't resume the run at all. It returns `status: "cancelled"` with the content `"Tool execution cancelled by user."`, and no model call is made. If you approve some tools and deny others, the run resumes: Agno executes the approved ones, skips the denied ones, and tells the model they were rejected.

The fields HiveGate accepts in each `updated_tools` entry are `confirmed`, `tool_args` (or `args`) and `confirmation_note`. Anything else is ignored.

## The same thing from Python

A minimal backend helper, with the review step left to your UI:

```python
import httpx

BASE = "http://localhost:8000/v2/agents/support-agent"
HEADERS = {"X-API-Key": HIVEGATE_KEY}

def chat(message: str, user: dict, session_id: str) -> dict:
    body = {
        "message": message,
        "user_id": user["profile_id"],
        "session_id": session_id,
        "timezone": "UTC",
        "locale": "en",
        "stream": False,
        "user_profile": user,
    }
    return httpx.post(f"{BASE}/chat", headers=HEADERS, json=body, timeout=120).json()

def decide(paused: dict, user: dict, decisions: list[dict]) -> dict:
    """decisions: one {"tool_call_id", "confirmed", optional "tool_args", "confirmation_note"} per pending tool."""
    body = {
        "run_id": paused["run_id"],
        "user_id": user["profile_id"],
        "session_id": paused["session_id"],
        "stream": False,
        "updated_tools": decisions,
    }
    response = httpx.post(f"{BASE}/chat/commit", headers=HEADERS, json=body, timeout=120)
    if response.status_code == 410:
        raise RuntimeError("Paused run is gone; ask the agent again.")
    response.raise_for_status()
    return response.json()

reply = chat("Cancel my 2pm with Jordan.", user, "inbox-1")
if reply["status"] == "PAUSED":
    pending = [t for t in reply["tools"] if t.get("requires_confirmation")]
    decisions = review_in_ui(pending)  # your code: returns approve/edit/deny per tool
    reply = decide(reply, user, decisions)
print(reply["content"])
```

If the chat request named a `model`, send the same `model` on commit. HiveGate uses it to find the paused agent.

## Where paused runs live

A paused run is held in the memory of the HiveGate process that paused it, until it's committed. If the process restarts, or the commit lands on a different replica, commit returns **410 Gone** ("Confirmation time window has elapsed"). Two practical consequences:

- Run a single replica, or route each session to the same instance, when you use approvals.
- Treat a 410 as "the proposal expired": ask the agent again rather than retrying the commit.

The conversation itself is stored in Postgres, so the user doesn't lose their history when a pending action expires.

## The audit trail

Here is what HiveGate records about a decision:

- **The run, in the agent's session.** Agno stores each run in the agent's Postgres session table. A resumed run's tool executions carry the arguments that actually ran (including any edits), `requires_confirmation`, `confirmed` and the `confirmation_note`.
- **The cost of the resumed run.** The resumed part is metered like any other call: a row in `token_usage` with the user, session, API key name, number of tool calls, status and USD cost. You can list them with `GET /usage/calls?agent=support-agent&order=recent`, which needs a key with the `usage:read` scope.
- **Logs.** Every commit is logged with its `run_id`, and a fully denied run is logged as such. Set `OTEL_TRACING_BACKEND=otlp` and `OTEL_LOGGING_BACKEND=otlp` (Sentry and Logtail are also supported) to send traces and logs to your observability stack.

What it doesn't record is *which person* clicked approve. HiveGate sees the API key that made the commit, not your end user's identity. If you need that for compliance, record the reviewer and the decision in your own database before you call commit. You can also put the reviewer in `confirmation_note`, which is stored with the tool execution. A fully denied run is never resumed, so it leaves no usage row. Your own record and the log line are the trace for those.

## A note on `/v2/approvals`

HiveGate also has an approvals inbox at `/v2/approvals`, used by the supervisor platform. `GET /v2/approvals` lists pending requests, and `POST /v2/approvals/{job_id}/approve`, `/deny` or `/decide` records a decision. It can push requests out through notification plugins (webhook, Slack, Telegram, Discord and WhatsApp are built in; `GET /v2/approvals/plugins/list` shows them). Those requests are also held in process memory. For the agent chat flow in this post, the commit call is what resumes the run.

## Try it

- Deploy HiveGate from the [deploy page](/deploy/). Create an agent tagged `available_tools:email`, store a test Gmail token for one user (see the [OAuth post](/blog/per-user-google-microsoft-oauth-ai-agents/)), and ask the agent to email you. The run will pause.
- The commit endpoint is in `api/routes/v2/agents.py` and the Agno resume logic is in `agents/hitl.py` in the [GitHub repo](https://github.com/hivegate-ai/hivegate).
