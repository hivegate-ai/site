---
title: "Claude prompt caching for agents: what breaks the cache"
description: "Agents re-send tools, system prompt and history on every round trip. How Claude prompt caching works for Agno agents, what breaks it, and how to check."
date: 2026-10-25
---

An agent turn is a loop. The model reads the tools, the system prompt and the conversation, calls a tool, reads the result and calls the model again. Every round trip re-sends everything before it. Anthropic's prompt caching exists for exactly this: the part of the request that hasn't changed since the last call is read from cache at a tenth of the input price.

Turning it on is one flag. Getting cache hits is a different matter. The cache only matches an identical prefix, and agent frameworks put things in the prefix that change on every request. You don't get an error when that happens. You get a bill with `cache_write_tokens` on every call and almost no `cache_read_tokens`.

This post covers how caching works for agents, the settings [HiveGate](https://github.com/hivegate-ai/hivegate) uses for Claude models, the things that quietly break the cache, and how to check your hit rate. HiveGate is an open-source FastAPI service that runs [Agno](https://github.com/agno-agi/agno) agents behind a REST API. Prompt caching landed on `main` in [#110](https://github.com/hivegate-ai/hivegate/pull/110) and isn't in a tagged release yet; the latest is v0.3.0.

## How Claude prompt caching works, briefly

A Claude request is rendered in a fixed order: tools, then the system prompt, then the messages. A `cache_control` marker on a block tells Anthropic to store everything up to and including that block. A later request whose prefix is identical up to that point reads it from cache instead of processing it again.

- **Identical means byte-identical.** One changed character in the system prompt, or one tool definition in a different order, and the prefix after it no longer matches.
- **Reads bill at 0.1x the input price, writes at 1.25x.** Writing the cache costs more than not caching. You save money only if the same prefix is read again.
- **The cache lives for 5 minutes,** and every read refreshes it. Anthropic also offers a 1-hour TTL, with writes billed at 2x input.
- **Short prompts aren't cached.** Below the model's minimum length (1024 tokens on Sonnet 4.6, 4096 on Haiku 4.5), the request is sent uncached, with no error.

For a chatbot that makes one call per turn, the gain is modest. An agent that makes four model calls per turn re-sends the same tools and system prompt four times, plus a conversation that grows with each tool result. That's where caching pays.

## The two breakpoints HiveGate sets

HiveGate builds every Claude model in `agents/model_factory.py` with two cache breakpoints:

```python
ANTHROPIC_PROMPT_CACHING: dict[str, Any] = {
    "cache_system_prompt": True,
    "request_params": {"cache_control": {"type": "ephemeral"}},
}
```

- `cache_system_prompt` is an option of Agno's `Claude` model. It marks the system prompt block. Tools render before the system prompt, so this one marker caches tools and system prompt together.
- The top-level `cache_control` in `request_params` is Anthropic's automatic caching. It marks the last block of the request and moves forward as the conversation grows, so each tool-loop round trip and each follow-up turn reads everything before it from cache.

Both use the 5-minute TTL. There's nothing to configure. A test (`tests/test_prompt_caching.py`) sends requests through a real `anthropic` client with a fake HTTP transport and checks that both markers are in the JSON body, for streamed and non-streamed calls. If an Agno or SDK upgrade stops sending them, the test fails.

The PR that added this notes that across all agents on our own deployment, 0% of input tokens had been cached in the previous 30 days. The flags were never set, which is the easy case. The harder cases are the ones where the flags are set and the cache still misses.

## What breaks the cache

### A timestamp in the system prompt

Agno can add the current time to the system prompt it builds for an agent. With `add_datetime_to_context=True`, the agent-built system message gets a line like this, from `str(datetime.now())`:

```
The current time is 2026-10-25 09:14:03.512347+03:00.
```

That string has microseconds in it. Agno builds the system message once per run, so the round trips inside one run still read each other's cache. The next run is different: new timestamp, new system block, no match. Every run starts with a write at 1.25x, for the tools, the system prompt and the whole conversation history after them. The prefix is never shared across runs or users, and an agent that makes one model call per turn pays more than with caching off.

A plain Agno agent like this one has that problem:

```python
from agno.agent import Agent
from agno.models.anthropic import Claude

agent = Agent(
    model=Claude(id="claude-sonnet-5-5", cache_system_prompt=True),
    instructions=["You are a support agent for Acme.", "..."],
    add_datetime_to_context=True,  # puts a new timestamp in the system prompt every run
    tools=[...],
)
```

HiveGate turns `add_datetime_to_context` on, but it also passes each agent's prompt as a fixed `system_message` string. When `system_message` is set, Agno returns it as the system prompt and skips building one, so the timestamp line is never added. Agents can still work with dates: every HiveGate agent gets a datetime resolver tool that turns "tomorrow" or "next Tuesday" into a date in the user's timezone, as a tool result inside the conversation, after the cached prefix.

If you run Agno yourself, the fix is the same idea. Either pass a fixed `system_message`, or set `add_datetime_to_context=False` and give the agent a tool that returns the time. If you need the date in the prompt, format it to the day (`datetime_format="%Y-%m-%d"`), so the prefix changes once a day instead of on every call.

### Per-user values in the prompt

Agno resolves `{placeholders}` in the system message from the session state by default (`resolve_in_context=True`). A prompt that starts with `You are helping {user_name}` gives every user their own prefix. The cache still works within one user's conversation, but the tools and instructions are no longer shared across users, and each new user pays the write.

Keep the shared part of the prompt fixed, and send per-user facts in the user message, where they come after the cached prefix. In HiveGate, prompts are stored as data and loaded by id, so the same template text goes out for every user of an agent.

### Tools that change per request

Tools come first in the request, so any change to the tool list changes the whole prefix. Two common causes:

- **Toolkits picked per user.** HiveGate selects the Gmail or Outlook toolkit for each run, depending on which OAuth token the user has connected (see [per-user OAuth](/blog/per-user-google-microsoft-oauth-ai-agents/)). Users on Google and users on Microsoft send different tool definitions, so each combination has its own cache entry. That's fine, as long as you expect it when you read the numbers.
- **MCP servers.** An MCP server's tool list is part of your prefix, and it can be large. An [Agno feature request](https://github.com/agno-agi/agno/issues/11218) reports that two production MCP servers with 30 tools add about 8,400 input tokens to every call. Cached, that's a 0.1x read on each round trip. If the server's tool list changes order or content between connections, it's a 1.25x write instead.

### Traffic slower than the TTL

The cache expires 5 minutes after its last read. An agent that gets one request every ten minutes writes the prefix every time and never reads it, so it pays 1.25x on that prefix instead of 1x. A conversation where the user takes a coffee break between turns pays the write again when they come back.

The break-even is low. With one write and one read inside five minutes, you pay 1.25 + 0.1 = 1.35 units instead of 2. Busy agents and long tool loops gain the most; rarely used agents gain nothing and lose a little.

### Editing the prompt

Changing an agent's prompt or tools changes the prefix, so the next run pays one write. That's expected and cheap. It only matters if something rewrites the prompt on every request, which brings you back to the first two sections.

## Check your hit rate

You don't have to guess whether caching works. HiveGate's usage meter ([#109](https://github.com/hivegate-ai/hivegate/pull/109)) records `cache_read_tokens` and `cache_write_tokens` for every model call, next to `input_tokens`. For Claude, `input_tokens` counts only the uncached part, so the share of input read from cache is:

```
cache_read_tokens / (input_tokens + cache_read_tokens + cache_write_tokens)
```

`/usage/summary` with `group_by=model` returns those totals per model. With a key that has the `usage:read` scope:

```sh
curl -s -H "X-API-Key: $USAGE_KEY" \
  "http://localhost:8000/usage/summary?window=7d&group_by=model" \
| jq '.groups[] | select(.key | startswith("claude"))
      | {model: .key, calls, cost_usd,
         cached_share: (.cache_read_tokens / ((.input_tokens + .cache_read_tokens + .cache_write_tokens) | if . == 0 then 1 else . end))}'
```

Swap `group_by=model` for `group_by=agent` to find the agent with the problem. What to look for:

- **`cache_write_tokens` close to `cache_read_tokens`, or higher.** Something in the prefix changes on most requests: a timestamp, a per-user placeholder, or a tool list that moves.
- **Both near zero.** The prompt is below the model's minimum, or the markers aren't being sent.
- **Reads much larger than writes.** Working as intended.

To look at single runs, `GET /usage/calls?window=24h&agent=<id>&order=recent` lists calls with their tokens, `session_id` and `run_id`. A run with four `model_requests` and a cache write on each one is the pattern to chase. The [token usage and cost tracking post](/blog/llm-token-usage-cost-tracking/) covers the meter, the scopes and the price table in detail.

## What it's worth

Take `claude-sonnet-5-5`, which HiveGate's price table lists at $2 per million input tokens, $0.20 for cache reads and $2.50 for cache writes. An agent has 12,000 tokens of tools and system prompt, and a typical turn makes three model calls. Counting only that prefix, for 1,000 turns spread through a working day:

- **Uncached:** 3 × 12,000 × 1,000 tokens at $2/M = $72.
- **Cached, with a timestamp in the system prompt:** one write and two reads per turn, (12,000 × $2.50/M + 2 × 12,000 × $0.20/M) × 1,000 = $34.80.
- **Cached, with a fixed prefix and steady traffic:** almost every call is a read, 3 × 12,000 × $0.20/M × 1,000 = $7.20, plus a write each time the cache expires.

That's arithmetic from the price table, not a benchmark, and the conversation part of each request adds to all three rows. Caching with a timestamp still beats no caching here, because each turn makes three calls. The difference between the second and third lines is one line of the system prompt.

## When you don't need HiveGate for this

If you run Agno agents in your own code, you can get the same result with two settings: `Claude(cache_system_prompt=True)` and a system prompt that doesn't change between runs. Add `request_params={"cache_control": {"type": "ephemeral"}}` for the conversation. Then measure with the `cache_read_tokens` Agno reports in the run metrics.

HiveGate is for the case where you also want the rest around it: agents and prompts stored as data, per-user sessions and OAuth tokens, and a per-call cost record you can group by user, tenant or agent.

## Try it

- Deploy HiveGate from the [deploy page](/deploy/), or run it from `main`. Use a Claude model (the [LLM models docs](/docs/llm-models/) list the ids and aliases such as `anthropic:sonnet-latest`), run a multi-step agent twice within five minutes, and call `/usage/summary?group_by=agent`.
- The caching settings are in `agents/model_factory.py`, the prices in `agents/pricing.py`, and the meter in `api/services/usage.py`, all in the [GitHub repo](https://github.com/hivegate-ai/hivegate).

If this is useful, a star helps other people find the project: [⭐ github.com/hivegate-ai/hivegate](https://github.com/hivegate-ai/hivegate).
