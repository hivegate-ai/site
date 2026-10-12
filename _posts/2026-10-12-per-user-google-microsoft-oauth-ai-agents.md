---
title: "Per-user Google and Microsoft OAuth for AI agents"
description: "How an AI agent can read and send from each user's own Gmail, Outlook and calendar: encrypted per-user token storage, automatic refresh, and toolkits."
date: 2026-10-12
---

An assistant that drafts replies or books meetings has to act inside *each user's* account. That means one set of OAuth tokens per user and per service. The access tokens expire roughly every hour and have to be refreshed, and the agent's tools need the right token at the moment they run, without the model ever seeing it.

This post walks through how [HiveGate](https://github.com/hivegate-ai/hivegate), an open-source FastAPI service for [Agno](https://github.com/agno-agi/agno) agents, does this for Gmail, Outlook, Google and Microsoft Calendar, Contacts, Google Drive and OneDrive.

## Who does what

HiveGate does **not** run the OAuth consent screen. Your app already has a sign-in flow and a registered Google or Microsoft OAuth client. You send the user through consent, exchange the code for tokens, and then hand the tokens to HiveGate. From that point HiveGate stores them encrypted, refreshes them, and gives them to the agent's tools.

The split keeps the redirect URIs, consent screen and client registration in your app, where they already are.

## Storing a user's tokens

After the code exchange, POST the tokens to `/v2/users/{user_id}/tokens`. The `user_id` is the same ID you send in chat requests.

```sh
curl -X POST http://localhost:8000/v2/users/user-1842/tokens \
  -H "X-API-Key: $HIVEGATE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "integration_key": "google_gmail",
    "provider": "google",
    "token_type": "oauth2",
    "token_data": {
      "access_token": "ya29.a0...",
      "refresh_token": "1//0g...",
      "expires_in": 3599,
      "token_type": "Bearer",
      "client_id": "1234-abc.apps.googleusercontent.com",
      "client_secret": "GOCSPX-..."
    },
    "scopes": ["https://www.googleapis.com/auth/gmail.modify"]
  }'
```

A few details that matter:

- **`integration_key` picks the toolkit.** The toolkits look tokens up under fixed keys: `google_gmail`, `google_calendar`, `google_contacts`, `google_drive`, and `outlook_mail`, `microsoft_calendar`, `microsoft_contacts`, `microsoft_drive`.
- **One record per key.** If one Google consent covers Gmail and Calendar, store the same tokens under both `google_gmail` and `google_calendar`. Each record refreshes on its own.
- **`provider` picks the refresh endpoint.** `google` refreshes against `oauth2.googleapis.com/token`, `microsoft` against `login.microsoftonline.com/common/oauth2/v2.0/token`.
- **Include `client_id` and `client_secret`.** They're stored with the token and sent on refresh. Without them, refresh fails for most providers.
- **`expires_in` becomes `expires_at`.** HiveGate computes the expiry time when it stores the token.

Posting again for the same user and key replaces the record. The table has a unique constraint on `(user_id, integration_key)`.

Here is the same thing in Python, right after your OAuth callback exchanges the code:

```python
import httpx

GOOGLE_KEYS = ("google_gmail", "google_calendar")

def save_google_tokens(user_id: str, tokens: dict, client_id: str, client_secret: str) -> None:
    """Store a Google token response in HiveGate under each integration it covers."""
    token_data = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token"),
        "expires_in": tokens.get("expires_in"),
        "token_type": tokens.get("token_type", "Bearer"),
        "client_id": client_id,
        "client_secret": client_secret,
    }
    for key in GOOGLE_KEYS:
        response = httpx.post(
            f"{HIVEGATE_URL}/v2/users/{user_id}/tokens",
            headers={"X-API-Key": HIVEGATE_KEY},
            json={
                "integration_key": key,
                "provider": "google",
                "token_type": "oauth2",
                "token_data": {k: v for k, v in token_data.items() if v is not None},
                "scopes": tokens.get("scope", "").split(),
            },
        )
        response.raise_for_status()
```

## How tokens are kept

Token data is encrypted with [Fernet](https://cryptography.io/en/latest/fernet/) before it's written to the `user_tokens` table. The key comes from the `SECRET_TOKEN_ENC_KEY` environment variable. Without it, storing a token fails with an encryption error. Generate one with:

```sh
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Keep the key in your secret manager. Losing it makes every stored token unreadable, and users will have to connect again.

Listing a user's tokens returns metadata only (integration, provider, scopes, expiry, `is_expired`), never the token values:

```sh
curl -H "X-API-Key: $HIVEGATE_KEY" http://localhost:8000/v2/users/user-1842/tokens
```

## How refresh works

You don't schedule refreshes. When a toolkit asks for a token, HiveGate loads the record and checks the expiry. If the token expires within the next 60 seconds, HiveGate refreshes it first, using the stored refresh token and client credentials, then saves the new access token and expiry. If the provider sends a new refresh token, that's saved too.

The refresh call is retried up to three times with exponential backoff on network errors, 429 and 5xx responses. A 400 or 401 is not retried, because it usually means the user revoked access or the refresh token is no longer valid. Retrying won't fix that, and the user needs to reconnect.

You can also force a refresh, which is useful to check that stored credentials still work:

```sh
curl -X POST -H "X-API-Key: $HIVEGATE_KEY" \
  http://localhost:8000/v2/users/user-1842/tokens/google_gmail/refresh
```

To disconnect a user from a service, delete the record:

```sh
curl -X DELETE -H "X-API-Key: $HIVEGATE_KEY" \
  http://localhost:8000/v2/users/user-1842/tokens/google_gmail
```

## How the toolkits pick a provider

Enable toolkits on an agent with an `available_tools` tag, for example `available_tools:email,calendar` when you create it. Then, **before every run**, a pre-hook checks in a single query which of the eight integration keys exist for this user, and gives the agent the right toolkit for each service:

- Google toolkit if a Google token exists,
- otherwise the Microsoft toolkit if a Microsoft token exists,
- otherwise a "not connected" toolkit.

The not-connected toolkit has one tool, such as `email_auth_required`, which returns a card like `{"card": "email-auth-required", "context": {"token_valid": false}}` and ends the run. Your UI can show a "Connect Gmail" button when it sees that card. When the user connects, the next message gets the real toolkit without rebuilding the agent.

The toolkits are scoped to the user in the request, so user A's agent can only load user A's tokens. The chat request has to carry a `user_profile`, because the toolkits are built only when the user's email is known (it's also used as the organizer for calendar invites):

```sh
curl -X POST http://localhost:8000/v2/agents/support-agent/chat \
  -H "X-API-Key: $HIVEGATE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Find the last email from billing@acme.example and draft a reply.",
    "user_id": "user-1842",
    "session_id": "inbox-1",
    "timezone": "Europe/London",
    "locale": "en-GB",
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

Inside a tool, the token is fetched through a small in-process cache keyed by service and user. Write operations on the calendar bypass the cache and fetch a fresh token. The token goes straight into the Google or Microsoft API call. It is never added to the prompt, so the model never sees it.

## What each toolkit can do

| Toolkit | Tools | Needs approval |
|---|---|---|
| Email (Gmail, Outlook) | `search_emails`, `list_drafts`, `send_email`, `create_draft`, `send_draft`, `trash_email`, `delete_email_permanently`, `modify_labels` | All except search and list |
| Calendar (Google, Microsoft) | `list_events`, `schedule_meeting`, `schedule_meeting_find_time`, `cancel_meeting` | Scheduling and cancelling |
| Contacts (Google, Microsoft) | `list_contacts`, `search_contacts`, `create_contact`, `update_contact`, `delete_contact` | Create, update, delete |
| Drive (Google Drive, OneDrive) | `list_files`, `get_file_info`, `read_file` | `read_file` |

"Needs approval" means the run pauses before the tool executes, and your app shows the user what the agent wants to do. The [post on approvals](/blog/human-approval-agent-tool-calls/) covers that flow.

## Things to get right

- **Keep the tokens API on your backend.** `GET /v2/users/{user_id}/tokens/{integration_key}` returns the decrypted token to any valid API key. Call HiveGate from your server, never from a browser or mobile app, and give that key only to the service that needs it.
- **Ask for narrow scopes.** Request only what the enabled tools need, for example `calendar.events` rather than full calendar access.
- **Handle the reconnect case.** When refresh fails with a 400 or 401, the tool returns an error result to the agent instead of crashing the run, and the failure is in the server log. Treat it as "ask the user to reconnect", and use the manual refresh endpoint to confirm.

Per-user authentication for MCP tool servers isn't built yet. It's on the [roadmap](https://github.com/hivegate-ai/hivegate/issues/72).

## Try it

- Deploy HiveGate in one click from the [deploy page](/deploy/), and set `SECRET_TOKEN_ENC_KEY` before you store your first token.
- The token API and toolkits are in the [GitHub repo](https://github.com/hivegate-ai/hivegate) under `api/routes/v2/tokens.py` and `toolkits/`.
