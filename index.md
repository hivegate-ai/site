---
title: "HiveGate — run your Agno agents as a production API"
description: "HiveGate is an open-source FastAPI service for AI agents: per-user sessions, OAuth tokens, approvals, multi-agent teams and tracing, with one-click deploys. Built on Agno. MIT licensed."
home: true
---

<section class="hero">
  <div class="hero-copy">
    <h1>Run your Agno agents as a production API.</h1>
    <p class="hero-lead">HiveGate is an open-source FastAPI service that gives your agents what production needs: per-user sessions, OAuth tokens, approvals, multi-agent teams and tracing. You write the agent. HiveGate serves it.</p>
    <div class="hero-actions">
      <a class="btn btn-primary" href="/deploy/" data-goatcounter-click="click_deploy" data-goatcounter-title="Hero — Deploy">Deploy in one click</a>
      <a class="btn btn-quiet" href="#quickstart" data-goatcounter-click="click_quickstart" data-goatcounter-title="Hero — Quickstart">Run it locally</a>
    </div>
    <p class="hero-meta">Free and open source under the MIT license. Python 3.11+, built on <a href="https://github.com/agno-agi/agno" rel="noopener">Agno</a>.</p>
  </div>
  <div class="hero-visual">
    {% include hive.svg %}
  </div>
</section>

<section class="band" aria-labelledby="api-heading">
  <div class="band-head">
    <h2 id="api-heading">Everything is an HTTP call</h2>
    <p>Your app talks to agents, teams, approvals and tokens through one REST API, with plain JSON or streamed responses.</p>
  </div>
  {% include api-examples.html %}
</section>

<section class="band" aria-labelledby="included-heading">
  <div class="band-head">
    <h2 id="included-heading">What you'd otherwise build yourself</h2>
    <p>Running an agent in a notebook is easy. Serving it to many users means building all of this around it. HiveGate ships it.</p>
  </div>
  <div class="included">
    <div class="included-group">
      <h3>Serving</h3>
      <dl>
        <dt><a href="/docs/api-agents/">Agents over HTTP</a></dt>
        <dd>Create, version and chat with agents through a REST API, with JSON or streamed replies.</dd>
        <dt><a href="/docs/overview/">Per-user sessions</a></dt>
        <dd>Conversation history is kept per user and per session, and separated by tenant.</dd>
        <dt><a href="/docs/api-teams/">Teams of agents</a></dt>
        <dd>Group agents into a team that coordinates, or one where a supervisor hands out the work.</dd>
      </dl>
    </div>
    <div class="included-group">
      <h3>Identity and integrations</h3>
      <dl>
        <dt><a href="/docs/authentication/">API keys</a></dt>
        <dd>Per-client API keys, plus a separate admin secret for management endpoints.</dd>
        <dt><a href="/docs/api-tokens/">OAuth token store</a></dt>
        <dd>Each user's Google and Microsoft tokens are stored and refreshed for you.</dd>
        <dt><a href="/docs/toolkits/">Workspace toolkits</a></dt>
        <dd>Ready-made Gmail, Calendar, Contacts and Drive tools for Google and Microsoft accounts.</dd>
      </dl>
    </div>
    <div class="included-group">
      <h3>Knowledge</h3>
      <dl>
        <dt><a href="/docs/api-knowledge/">Knowledge base</a></dt>
        <dd>Per-tenant documents your agents can search, stored in Qdrant.</dd>
        <dt><a href="/docs/api-prompts/">Versioned prompts</a></dt>
        <dd>Edit an agent's prompt through the API without redeploying. Every change gets a new version number.</dd>
        <dt><a href="/docs/api-skills/">Skills</a></dt>
        <dd>Reusable step-by-step instructions, reference material and scripts that agents can follow.</dd>
      </dl>
    </div>
    <div class="included-group">
      <h3>Operations</h3>
      <dl>
        <dt><a href="/docs/api-approvals/">Approvals</a></dt>
        <dd>Risky tool calls pause until a person approves or denies them.</dd>
        <dt><a href="/docs/configuration/">Tracing and errors</a></dt>
        <dd>OpenTelemetry, Sentry and Logtail, switched on with environment variables.</dd>
        <dt><a href="/deploy/">Deploy anywhere</a></dt>
        <dd>A prebuilt image for Render, Railway, Koyeb, Kubernetes, AWS, Azure and Google Cloud.</dd>
      </dl>
    </div>
  </div>
</section>

<section class="band band-split" aria-labelledby="run-heading">
  <div class="band-head">
    <h2 id="run-heading">How a team run works</h2>
    <p>The hive at the top of this page, step by step.</p>
  </div>
  <ol class="steps">
    <li>
      <h3>A request comes in</h3>
      <p>Your app sends a message to a team, along with who the user is and which tenant they belong to.</p>
    </li>
    <li>
      <h3>The supervisor splits the work</h3>
      <p>A supervisor agent decides which agents in the team should handle each part of the request.</p>
    </li>
    <li>
      <h3>Workers act for the user</h3>
      <p>Each agent calls its tools, such as Gmail, Calendar or the knowledge base, using that user's own tokens.</p>
    </li>
    <li>
      <h3>Risky actions wait for a person</h3>
      <p>Anything marked as needing approval pauses the run until someone approves or denies it.</p>
    </li>
    <li>
      <h3>One answer comes back</h3>
      <p>The team replies as JSON or a stream. Every step is traced, so you can see what happened afterwards.</p>
    </li>
  </ol>
</section>

<section class="band" id="quickstart" aria-labelledby="quickstart-heading">
  <div class="band-head">
    <h2 id="quickstart-heading">Run it locally in five minutes</h2>
    <p>You need Docker, Python 3.11+ and an API key for a model provider. The demo agent uses Gemini.</p>
  </div>
  <div class="quickstart">
    <ol class="steps steps-code">
      <li>
        <h3>Clone it and add your key</h3>
<pre><code>git clone https://github.com/hivegate-ai/hivegate
cd hivegate
cp .env.example .env</code></pre>
        <p>In <code>.env</code>, set <code>GOOGLE_API_KEY</code> and uncomment <code>AUTH_DISABLED=true</code> for local use. The server reads <code>.env</code> when it starts, so do this first.</p>
      </li>
      <li>
        <h3>Start the databases and the API</h3>
<pre><code>docker compose up -d
./scripts/dev_setup.sh
source .venv/bin/activate
./scripts/start_server.sh</code></pre>
        <p>This starts Postgres and Qdrant and loads some demo agents.</p>
      </li>
      <li>
        <h3>Chat with the demo agent</h3>
<pre><code>curl -X POST \
  http://localhost:8000/v2/agents/demo-assistant/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Hi", "user_id": "u1",
       "session_id": "s1", "stream": false}'</code></pre>
        <p>Interactive API docs are at <code>http://localhost:8000/docs</code>.</p>
      </li>
    </ol>
    <aside class="quickstart-aside" aria-labelledby="oneclick-heading">
      <h3 id="oneclick-heading">Rather skip the setup?</h3>
      <p>Deploy the prebuilt image to a managed platform. You'll be asked for a database and your model API key.</p>
      {% include deploy-buttons.html %}
      <p class="small"><a href="/deploy/">Deploy guide</a>, with Kubernetes and cloud setups.</p>
    </aside>
  </div>
</section>

<section class="band" id="deploy" aria-labelledby="deploy-heading">
  <div class="band-head">
    <h2 id="deploy-heading">Where it runs</h2>
    <p>Every option uses the same image, <code>ghcr.io/hivegate-ai/hivegate</code>, built for both x86 and ARM.</p>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr><th scope="col">Platform</th><th scope="col">Good for</th><th scope="col">Config</th></tr></thead>
      <tbody>
        <tr><th scope="row">Render</th><td>The easiest first deploy</td><td><a href="https://github.com/hivegate-ai/deploy/blob/main/render.yaml"><code>render.yaml</code></a></td></tr>
        <tr><th scope="row">Railway</th><td>The smoothest Postgres setup</td><td><a href="https://github.com/hivegate-ai/deploy/blob/main/railway.toml"><code>railway.toml</code></a></td></tr>
        <tr><th scope="row">Koyeb</th><td>Trying it on a free tier</td><td><a href="https://github.com/hivegate-ai/deploy/blob/main/koyeb.yaml"><code>koyeb.yaml</code></a></td></tr>
        <tr><th scope="row">Kubernetes</th><td>Self-hosting and scaling</td><td><a href="https://github.com/hivegate-ai/deploy/tree/main/k8s">Kustomize manifests</a></td></tr>
        <tr><th scope="row">AWS, Azure, Google Cloud</th><td>Your own cloud account</td><td><a href="https://github.com/hivegate-ai/hivegate/tree/main/deploy">ECS, Container Apps, Cloud Run</a></td></tr>
      </tbody>
    </table>
  </div>
</section>

<section class="band" id="faq" aria-labelledby="faq-heading">
  <div class="band-head">
    <h2 id="faq-heading">Questions</h2>
  </div>
  <div class="faq">
    <details>
      <summary>Is it production-ready?</summary>
      <p>Yes, with caveats. The API, supervisor, job queue and toolkits are covered by an integration test suite that runs against real Postgres and Qdrant on every change. Choose your observability backend and review authentication before exposing it to end users.</p>
    </details>
    <details>
      <summary>How does it relate to Agno?</summary>
      <p>HiveGate runs on top of <a href="https://github.com/agno-agi/agno" rel="noopener">Agno</a>. Agno provides the agent itself: model calls, tools and memory. HiveGate adds the HTTP API, multi-tenancy, storage, supervisor teams, OAuth tokens and the operational side.</p>
    </details>
    <details>
      <summary>Is it an API gateway like Kong?</summary>
      <p>No. Despite the name, HiveGate doesn't route traffic between services. It runs AI agents and exposes them over a REST API.</p>
    </details>
    <details>
      <summary>Which models can I use?</summary>
      <p>Any model Agno supports, including OpenAI, Anthropic (Claude) and Gemini. Set the model per agent, or per request with the <code>model</code> field.</p>
    </details>
    <details>
      <summary>Do I need a vector database?</summary>
      <p>Only for the knowledge base. Qdrant comes with the Docker Compose setup, but chat works without it.</p>
    </details>
    <details>
      <summary>Can I run it without Docker?</summary>
      <p>Yes. You need Postgres 14 or later, and Qdrant if you use the knowledge base, reachable over the network. See the <a href="/deploy/">deploy guide</a>.</p>
    </details>
  </div>
</section>
