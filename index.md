---
title: "HiveGate — open-source FastAPI gateway for AI agents"
description: "Open-source FastAPI gateway for serving, orchestrating, and deploying AI agents. Multi-agent teams, OAuth toolkits, observability, one-click deploy. Built on Agno. MIT licensed."
---

<section class="hero" markdown="1">

# HiveGate

<p class="lead">
Open-source <strong>FastAPI gateway for AI agents</strong> — serve, orchestrate, and deploy production AI agents on top of <a href="https://github.com/agno-agi/agno">Agno</a>. MIT licensed.
</p>

<div class="cta-row primary">
  <a class="btn" href="#quickstart" data-goatcounter-click="click_quickstart" data-goatcounter-title="Hero — Quickstart">⚡ Quickstart</a>
  <a class="btn" href="https://github.com/hivegate-ai/hivegate" rel="noopener" data-goatcounter-click="click_github_star" data-goatcounter-title="Hero — Star on GitHub">⭐ Star on GitHub</a>
  <a class="btn secondary" href="/docs/" data-goatcounter-click="click_docs" data-goatcounter-title="Hero — Read the docs">📖 Read the docs</a>
</div>

<div class="trust-badges">
  <a href="https://github.com/hivegate-ai/hivegate/stargazers" rel="noopener" data-goatcounter-click="click_github_star" data-goatcounter-title="Trust badge — GitHub stars"><img alt="GitHub stars" src="https://img.shields.io/github/stars/hivegate-ai/hivegate?style=social"></a>
  <a href="https://github.com/hivegate-ai/hivegate/blob/main/LICENSE" rel="noopener"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-yellow"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11+-blue">
  <a href="https://github.com/hivegate-ai/hivegate/pkgs/container/hivegate" rel="noopener"><img alt="GHCR image" src="https://img.shields.io/badge/image-ghcr.io%2Fhivegate--ai%2Fhivegate-2496ED?logo=docker&logoColor=white"></a>
  <img alt="Built on Agno" src="https://img.shields.io/badge/built%20on-Agno-7c9cff">
</div>

</section>

## The problem

Most production AI agents start as Python scripts that work fine in a notebook. **Shipping them to production is a different problem entirely**: API auth, per-user OAuth tokens, prompt versioning, multi-tenant isolation, job queues, approval flows, observability. Building all of that for every project doesn't scale.

HiveGate is the runtime that handles those layers, so your agent code stays focused on the agent.

## Why HiveGate? {#why}

A focused production scaffold around the Agno agent framework.

<div class="features">
  <div class="feature">
    <h3>REST API for agents</h3>
    <p>Create, configure, version, and chat with agents over HTTP. Per-user sessions, streaming or non-streaming, multi-tenant by design.</p>
  </div>
  <div class="feature">
    <h3>Multi-agent teams</h3>
    <p>Compose agents into teams with <strong>coordinate</strong> or <strong>supervisor</strong> execution modes. Job queues, approval flows, containerized workers.</p>
  </div>
  <div class="feature">
    <h3>OAuth toolkits</h3>
    <p>Plug Gmail, Calendar, Contacts, and Drive (Google + Microsoft) into any agent with confirmation workflows and auto-refresh.</p>
  </div>
  <div class="feature">
    <h3>Production-ready ops</h3>
    <p>OpenTelemetry tracing, Sentry, OTLP, Logtail. Versioned prompts. Per-tenant knowledge base on Qdrant.</p>
  </div>
  <div class="feature">
    <h3>One-click deploy</h3>
    <p>Render, Railway, Koyeb buttons backed by a prebuilt multi-arch image on GHCR. K8s manifests + AWS/Azure/GCP recipes included.</p>
  </div>
  <div class="feature">
    <h3>Open by default</h3>
    <p>MIT licensed. No vendor lock-in. Bring your own model provider (OpenAI, Anthropic, Gemini, …) and your own database.</p>
  </div>
</div>

## Quickstart — deploy in 5 minutes {#quickstart}

```sh
git clone https://github.com/hivegate-ai/hivegate
cd hivegate

# Start PostgreSQL + Qdrant (seeds demo agents automatically)
docker compose up -d

# Set up Python environment + start the API
./scripts/dev_setup.sh && source .venv/bin/activate
./scripts/start_server.sh
```

Then chat with the demo agent:

```sh
export GOOGLE_API_KEY="your-gemini-key"

curl -X POST http://localhost:8000/v2/agents/demo-assistant/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hi","user_id":"u1","session_id":"s1","stream":false}'
```

Interactive API docs at `http://localhost:8000/docs`. Full [quickstart guide](/docs/#quickstart) and [API reference](/docs/#api) →

### Or deploy to the cloud with one click

<div class="deploy-buttons">
  <a href="https://railway.app/template?template=https://github.com/hivegate-ai/deploy" rel="noopener" data-goatcounter-click="click_deploy" data-goatcounter-title="Deploy on Railway">
    <img alt="Deploy on Railway" src="https://railway.app/button.svg">
  </a>
  <a href="https://render.com/deploy?repo=https://github.com/hivegate-ai/deploy" rel="noopener" data-goatcounter-click="click_deploy" data-goatcounter-title="Deploy to Render">
    <img alt="Deploy to Render" src="https://render.com/images/deploy-to-render-button.svg">
  </a>
  <a href="https://app.koyeb.com/deploy?type=git&repository=github.com/hivegate-ai/deploy" rel="noopener" data-goatcounter-click="click_deploy" data-goatcounter-title="Deploy to Koyeb">
    <img alt="Deploy to Koyeb" src="https://img.shields.io/badge/Deploy%20to-Koyeb-121212?style=for-the-badge&logo=koyeb&logoColor=white">
  </a>
</div>

## Who is this for? {#who}

<div class="audience">
  <div class="persona">
    <h3>AI engineers</h3>
    <p>Building production agent systems and tired of stitching FastAPI + Postgres + Qdrant + OAuth boilerplate for every project.</p>
  </div>
  <div class="persona">
    <h3>Startups</h3>
    <p>Shipping agent APIs and want a permissive, MIT-licensed runtime they own — not a managed service with usage-based pricing.</p>
  </div>
  <div class="persona">
    <h3>Platform teams</h3>
    <p>Standing up an internal agent platform with multi-tenant isolation, approvals, and observability across many agent use cases.</p>
  </div>
  <div class="persona">
    <h3>Agno users</h3>
    <p>Already building on Agno and want the missing production layer — sessions, tokens, prompts, queues — without re-inventing it.</p>
  </div>
</div>

## Deploy options {#deploy}

| Path | Best for | Config |
|---|---|---|
| **Render** | Easiest first deploy | [`render.yaml`](https://github.com/hivegate-ai/deploy/blob/main/render.yaml) (image-based) |
| **Railway** | Best Postgres UX | [`railway.toml`](https://github.com/hivegate-ai/deploy/blob/main/railway.toml) |
| **Koyeb** | Free nano tier | [`koyeb.yaml`](https://github.com/hivegate-ai/deploy/blob/main/koyeb.yaml) |
| **Kubernetes** | Self-hosting / scale | [Kustomize manifests](https://github.com/hivegate-ai/deploy/tree/main/k8s) |
| **AWS / Azure / GCP** | Cloud-native | [`deploy/`](https://github.com/hivegate-ai/hivegate/tree/main/deploy) (ECS, Container Apps, Cloud Run) |

Full per-platform playbook with smoke tests and teardown: [Deploy guide](/deploy/) →

## Get started {#cta}

<div class="cta-row final">
  <a class="btn" href="https://github.com/hivegate-ai/hivegate" rel="noopener" data-goatcounter-click="click_github_star" data-goatcounter-title="Footer CTA — Star on GitHub">⭐ Star on GitHub</a>
  <a class="btn" href="/docs/" data-goatcounter-click="click_docs" data-goatcounter-title="Footer CTA — Read the docs">📖 Read the docs</a>
  <a class="btn" href="/deploy/" data-goatcounter-click="click_deploy" data-goatcounter-title="Footer CTA — Deploy guide">🚀 Deploy in 5 min</a>
</div>

<p class="cta-note">MIT licensed. Contributions welcome — see <a href="https://github.com/hivegate-ai/hivegate/issues" rel="noopener">issues</a> on GitHub.</p>

## FAQ

### Is it production-ready?
Yes, with caveats. The gateway, supervisor, queue, and toolkits are covered by an integration test suite that runs against real Postgres + Qdrant on every push. Pick your own observability backend and harden the auth before shipping to end users.

### How does it relate to Agno?
HiveGate is a service layer **on top of** [Agno](https://github.com/agno-agi/agno). Agno provides the agent primitives — LLM calls, tools, sessions. The gateway provides the HTTP API, multi-tenancy, persistence, supervisor orchestration, OAuth tokens, and operational surface.

### Is it a request-routing API gateway like Kong?
No. Despite the name, HiveGate is an **agent runtime**, not an HTTP request router. It serves and orchestrates AI agents over a REST API; it doesn't proxy traffic between services.

### What models does it support?
Anything Agno supports — OpenAI, Anthropic (Claude), Gemini, plus other providers via Agno. Configure per agent via the `model` field.

### Does it need a vector database?
Qdrant is bundled via docker-compose for the knowledge base. If you're not using knowledge entries, you can run without it. The chat path doesn't depend on Qdrant.

### Can I run it without Docker?
Yes — you need Postgres 14+ and (optionally) Qdrant reachable over the network. See the [deploy guide](/deploy/).
