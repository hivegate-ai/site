---
title: "LLM token usage and cost tracking per user and tenant"
description: "Record the tokens and USD cost of every model call your agents make, query it by user, tenant or agent, and cut Claude input costs with prompt caching."
date: 2026-10-18
---

An agent turn is rarely one model call. The model reads the tools and the system prompt, calls a tool, reads the result, calls another tool, and only then answers. Every one of those round trips re-sends everything before it. A support agent that looks harmless in testing can cost far more for the user who keeps it busy all day, and a run that fails after three round trips is still billed.

Your provider's dashboard shows one number per API key. It doesn't know which of your users, tenants or agents spent it. If you want to bill, cap or simply understand that spend, you need the cost of each call recorded next to who made it.

This post shows how that works in [HiveGate](https://github.com/hivegate-ai/hivegate), an open-source FastAPI service for [Agno](https://github.com/agno-agi/agno) agents: what gets recorded, how to query it, how prices are applied, and how Claude prompt caching changes the numbers. Both features landed on `main` this month ([#109](https://github.com/hivegate-ai/hivegate/pull/109) and [#110](https://github.com/hivegate-ai/hivegate/pull/110)). They are not in a tagged release yet; the latest is v0.3.0.

## First: you may already have this

If every model call already goes through an LLM proxy or an observability tool that prices calls, such as LiteLLM, Langfuse or Helicone, you have per-call cost data. Tag those calls with your user and tenant ids and you may not need anything else.

HiveGate's meter is for the case where the agents run inside HiveGate and you want the cost in the same Postgres database as the sessions, keyed by the same `user_id`, `session_id` and `tenant_id`, without running another service.

## What gets recorded

Every chat, commit, MCP and team run writes one row to the `token_usage` table. That includes streamed and non-streamed runs, and also runs that failed, were refused, or were abandoned when the client hung up. A row has:

- **Who:** `agent_id`, `user_id`, `session_id`, `run_id`, `tenant_id`, and the `api_key_name` that made the request.
- **Tokens:** `prompt_tokens`, `completion_tokens`, `cache_read_tokens`, `cache_write_tokens` and `reasoning_tokens`.
- **Work:** `model_requests` (round trips), `tool_calls`, `duration_ms` and `ttft_ms` (time to first token).
- **Money:** `cost_usd`, the `prices_version` it was priced with, and `unpriced_models` for anything the price table doesn't know.
- **Outcome:** `status`, one of `completed`, `paused`, `cancelled`, `error` or `refused`, plus the error text, which stays server-side.
- **Breakdown:** a JSONB `breakdown` that splits the cost per model type, so the main model, the memory model and the compression model are each priced at their own rate.

`tenant_id` comes from the request's `tenant_profile.tenant_id`, or from `user_profile.tenant_id` if there's no tenant profile. Send it on every chat request and you can group by tenant later.

Failed runs are recorded with their real tokens on purpose. A run that errors after the model was called is still billed by the provider, and a client retrying such a run in a loop can spend a lot without anyone noticing. A run that pauses for [human approval](/blog/human-approval-agent-tool-calls/) is recorded as `paused`, and the resumed part gets its own row when it's committed.

Recording runs off the event loop in a thread pool with its own database session, and it never fails the caller's request. If the write fails, the error is logged and the user still gets their answer.

## The cost of a single call

A non-streaming chat response carries the usage of that call in `token_usage` (trimmed):

```json
{
  "status": "completed",
  "content": "Your order shipped on Tuesday.",
  "token_usage": {
    "input_tokens": 412,
    "output_tokens": 86,
    "cache_read_tokens": 8240,
    "cache_write_tokens": 388,
    "reasoning_tokens": 0,
    "model_requests": 2,
    "model": "claude-sonnet-5-5",
    "cost_usd": 0.004302,
    "unpriced_models": null,
    "status": "completed"
  }
}
```

The numbers above are an example, not a measurement, but the fields are the real ones. That's enough to show a running total in your own UI, or to stop a session when it crosses a budget you set.

## A key that can read usage and nothing else

The `/usage` endpoints accept an API key with the `usage:read` scope (or `admin`), or the `X-Admin-Secret` header. Create a key for your dashboard with the admin API (see [API keys in the admin docs](/docs/api-admin/)):

```sh
curl -X POST http://localhost:8000/admin/api-keys \
  -H "X-Admin-Secret: $ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"name": "usage-dashboard", "owner_id": "finance", "scopes": ["usage:read"]}'
```

The raw key is in the `api_key` field of the response, and it's shown only once. A key whose only scope is `usage:read` is refused on every `/v2` route with a 403, so a key you hand to a dashboard can't call agents and spend tokens.

## Which users cost the most

`GET /usage/summary` returns the totals for a window and a breakdown by one dimension. `window` is one of `1h`, `6h`, `24h`, `7d` or `30d`, and `group_by` is one of `agent`, `tenant`, `model`, `api_key`, `user` or `status`:

```sh
curl -H "X-API-Key: $USAGE_KEY" \
  "http://localhost:8000/usage/summary?window=7d&group_by=user"
```

Each group, and the totals, has `calls`, `cost_usd`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `reasoning_tokens`, `model_requests`, `failed_calls` and `failed_cost_usd`. Groups are sorted by cost, most expensive first. The response also has `model_types`, the cost split between the main model and helper models such as the memory model, which is where unexpected spend often hides.

Swap `group_by=user` for `tenant` to see the cost per customer, or for `status` to see how much you paid for runs that failed.

## The most expensive calls

`GET /usage/calls` lists individual calls, the most expensive first by default:

```sh
curl -H "X-API-Key: $USAGE_KEY" \
  "http://localhost:8000/usage/calls?window=24h&tenant=acme&min_cost=0.05&limit=20"
```

You can filter by `agent`, `tenant`, `status` and `min_cost`, and set `order=recent` to get the newest first. Every call carries its `session_id` and `run_id`, so you can open the conversation that produced it and see why it took twelve round trips.

Two more endpoints cover dashboards:

- `GET /usage/timeseries?window=7d&bucket=1d&group_by=agent` returns the cost per time bucket for the top groups by cost (8 by default, `top` goes up to 20). The rest are folded into `(other)` so a chart stays readable.
- `GET /usage/live?after_id=0` returns the latest calls, oldest first. Poll it again with the `last_id` from the response to get only what's new.

## How prices are applied

Costs come from the price table in `agents/pricing.py`, in USD per million tokens, for Anthropic, Gemini and OpenAI models. `GET /usage/prices` returns the table that's in use.

Providers count tokens differently, and the meter follows each convention. Anthropic reports cache reads and writes separately from `input_tokens`. Gemini and OpenAI include cached tokens inside `input_tokens`, so the meter subtracts them before applying the full input price. Gemini reports thinking tokens separately and bills them at the output rate.

A model that isn't in the table is never guessed. Its calls are stored with `cost_usd` set to null and the model listed in `unpriced_models`. The summary counts those in `unpriced_calls` and `partially_priced_calls`. When either is above zero, read `cost_usd` as a lower bound, not a total.

To add or correct a price without a redeploy, set `PRICING_OVERRIDES`:

```sh
PRICING_OVERRIDES='{"my-model": {"input": 5, "output": 25, "cache_read": 0.5, "cache_write": 6.25}}'
```

## Prompt caching for Claude models

Each round trip of an agent re-sends the tools, the system prompt and the whole conversation so far. Without caching, all of that bills at the full input price every time. The PR that turned caching on ([#110](https://github.com/hivegate-ai/hivegate/pull/110)) notes that on our own deployment, 0% of input tokens had been cached across all agents in the previous 30 days, and one agent was sending about 50K input tokens per run.

Claude models in HiveGate now run with two cache breakpoints, set in `agents/model_factory.py`:

```python
ANTHROPIC_PROMPT_CACHING: dict[str, Any] = {
    "cache_system_prompt": True,
    "request_params": {"cache_control": {"type": "ephemeral"}},
}
```

- `cache_system_prompt` marks the system prompt. Tools render before it, so the tools and the system prompt are cached together. HiveGate passes a fixed system message per agent, so that prefix is shared by every run of the agent, across users.
- The top-level `cache_control` is Anthropic's automatic caching. It marks the last block and moves forward as the conversation grows, so each tool-loop round trip and each follow-up turn reads everything before it from cache.

There's nothing to configure. Both breakpoints use the 5-minute TTL, and each read refreshes it. A prompt shorter than the model's minimum cacheable length (1024 tokens on Sonnet 4.6, 4096 on Haiku 4.5) is simply sent uncached, with no error.

## What caching does to the bill

Cache reads bill at a fraction of the input price, and cache writes at 1.25x. For `claude-sonnet-5-5`, the price table has $2 per million input tokens, $0.20 for cache reads and $2.50 for cache writes.

Take an agent whose tools and system prompt add up to 10,000 tokens, and a turn with four round trips. Counting only that prefix:

- **Uncached:** 4 × 10,000 tokens × $2/M = $0.080.
- **Cached:** one write, 10,000 × $2.50/M = $0.025, then three reads, 3 × 10,000 × $0.20/M = $0.006. Total $0.031.

That's arithmetic from the price table, not a benchmark. The conversation part grows with every round trip and is cached the same way, so long tool loops gain the most. The cache lives for five minutes after its last read: an agent nobody has used for longer pays the write again, and so does a conversation that sat idle.

You don't have to trust the arithmetic. The meter records `cache_read_tokens` and `cache_write_tokens` for every call, so `/usage/summary?group_by=agent` shows, per agent, how much of the input came from cache and what it cost.

## Upgrading an existing database

On a fresh install, HiveGate creates the `token_usage` table with all the columns on startup. An existing database needs the new columns from `db/migrations/011_token_usage_cost.sql`. Every statement is `ADD COLUMN IF NOT EXISTS`, and existing rows keep working:

```sh
psql "$DATABASE_URL" -f db/migrations/011_token_usage_cost.sql
```

For history from before the meter existed, `scripts/usage_from_runs.py` builds a read-only per-agent cost report from Agno's stored runs.

## Try it

- Deploy HiveGate from the [deploy page](/deploy/), or run it locally from `main`. Create a `usage:read` key, send a few chat requests with a `user_id` and a `tenant_profile`, and call `/usage/summary?group_by=user`.
- The meter is in `api/services/usage.py`, the queries in `db/usage_queries.py` and the prices in `agents/pricing.py`, all in the [GitHub repo](https://github.com/hivegate-ai/hivegate#usage-and-cost). The [Agno deploy post](/blog/deploy-agno-agents-production-rest-api/) covers sessions, API keys and streaming.

If this is useful, a star helps other people find the project: [⭐ github.com/hivegate-ai/hivegate](https://github.com/hivegate-ai/hivegate).
