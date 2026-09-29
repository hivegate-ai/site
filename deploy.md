---
title: "Deploy — HiveGate"
description: "One-click deploy to Render, Railway, or Koyeb. Kubernetes via Kustomize. Cloud manifests for AWS, Azure, GCP."
permalink: /deploy/
---

# Deploy

All deploy paths are driven from [`hivegate-ai/deploy`](https://github.com/hivegate-ai/deploy) and pull the prebuilt multi-arch image **`ghcr.io/hivegate-ai/hivegate:latest`** (linux/amd64 + linux/arm64).

## One-click platform deploys {#one-click}

<div class="deploy-buttons">
  <a href="https://railway.app/template?template=https://github.com/hivegate-ai/deploy" rel="noopener">
    <img alt="Deploy on Railway" src="https://railway.app/button.svg">
  </a>
  <a href="https://render.com/deploy?repo=https://github.com/hivegate-ai/deploy" rel="noopener">
    <img alt="Deploy to Render" src="https://render.com/images/deploy-to-render-button.svg">
  </a>
  <a href="https://app.koyeb.com/deploy?type=git&repository=github.com/hivegate-ai/deploy" rel="noopener">
    <img alt="Deploy to Koyeb" src="https://img.shields.io/badge/Deploy%20to-Koyeb-121212?style=for-the-badge&logo=koyeb&logoColor=white">
  </a>
</div>

| Platform | Config | Mechanism | Recommended for |
|---|---|---|---|
| **Render** | `render.yaml` | `runtime: image`, pulls GHCR image directly | First try — easiest |
| **Railway** | `railway.toml` + wrapper `Dockerfile` | Image-only deploys via wrapper | Best Postgres UX |
| **Koyeb** | `koyeb.yaml` | `docker.image:` pulls GHCR image | Free nano tier |

All three default to `PROMPT_STORAGE_BACKEND=postgres` and prompt you for DB credentials and at least one LLM API key at deploy time.

Full step-by-step (provisioning Postgres, env vars, smoke test, teardown): [`DEPLOY_TEST_PLAN.md`](https://github.com/hivegate-ai/deploy/blob/main/DEPLOY_TEST_PLAN.md).

## Kubernetes {#k8s}

Kustomize-based, with base manifests under `k8s/base/` and per-project overlays. Deploy from the action workflow:

```bash
gh workflow run deploy-k8s.yml \
  -f project=hivegate \
  -f environment=production \
  -f image_tag=latest
```

Requires a `KUBECONFIG_HIVEGATE` secret (base64-encoded kubeconfig). For GKE workload-identity auth, see [`config/projects.yaml`](https://github.com/hivegate-ai/deploy/blob/main/config/projects.yaml).

## Cloud-specific manifests {#cloud}

Maintained alongside the app in [`hivegate-ai/hivegate/deploy/`](https://github.com/hivegate-ai/hivegate/tree/main/deploy):

| Target | Path |
|---|---|
| AWS (ECS + CloudFormation) | [`deploy/aws/`](https://github.com/hivegate-ai/hivegate/tree/main/deploy/aws) |
| Azure (Container Apps + Bicep) | [`deploy/azure/`](https://github.com/hivegate-ai/hivegate/tree/main/deploy/azure) |
| Google Cloud Run | [`deploy/gcp/`](https://github.com/hivegate-ai/hivegate/tree/main/deploy/gcp) |
| Generic (docker-compose, plain K8s) | [`deploy/generic/`](https://github.com/hivegate-ai/hivegate/tree/main/deploy/generic) |

## Smoke test {#smoke}

After deploy, run this against your service URL to confirm DB + LLM end-to-end:

```bash
URL=https://your-deployed-service.example.com

# 1. health
curl -fsS "$URL/health"

# 2. proves DB connectivity + ORM table auto-create
curl -fsS "$URL/v2/agents"

# 3. create a test agent (assumes AUTH_DISABLED=true, or pass -H "X-API-Key: <key>")
curl -fsS -X POST "$URL/v2/agents" \
  -H 'Content-Type: application/json' \
  -d '{"id":"smoke","name":"Smoke","template":"Reply with the single word: pong."}'

# 4. real LLM call through the deployed gateway
curl -fsS -X POST "$URL/v2/agents/smoke/chat" \
  -H 'Content-Type: application/json' \
  -d '{"message":"Reply with pong","user_id":"u","session_id":"s","timezone":"UTC","locale":"en","model":"gemini-2.5-flash-lite","stream":false}'

# 5. cleanup
curl -fsS -X DELETE "$URL/v2/agents/smoke"
```

Expected: each step returns `2xx`, step 4 echoes the Gemini reply (`"pong"`). Anything else → save logs and [open an issue](https://github.com/hivegate-ai/hivegate/issues).

## Operational notes {#ops}

- **Cold-start latency** on the first chat (~10–30 s while Agno loads and makes the first provider call). Subsequent chats are fast.
- **Postgres connection refused** at first boot if the DB isn't ready yet. Set `WAIT_FOR_DB=true` if your platform's DB takes a moment to provision.
- **Render free Postgres** has a connection cap (~5) and pauses after 30 days idle — fine for a smoke test, not for prod.
- **Koyeb secret resolution** fails the whole deploy if one referenced secret is missing — create even the ones you don't use, with an empty string.
- **GHCR rate limits** for unauthenticated pulls are generous, but if you're rebuilding in CI, log into GHCR with a PAT.
