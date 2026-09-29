# hivegate-ai/site

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Source](https://img.shields.io/badge/Source-hivegate--ai%2Fhivegate-181717.svg?logo=github)](https://github.com/hivegate-ai/hivegate)

Public landing site and documentation portal for [**HiveGate**](https://github.com/hivegate-ai/hivegate).

Built as a Jekyll site, served by GitHub Pages at <https://hivegate.dev>.

This repo is the marketing / SEO / LLM-discoverability surface. The app itself lives in [`hivegate-ai/hivegate`](https://github.com/hivegate-ai/hivegate); deploy artifacts in [`hivegate-ai/deploy`](https://github.com/hivegate-ai/deploy).

## Why a dedicated repo

- **Discoverability** — a real domain (`hivegate.dev`) outranks `*.github.io` paths in Google + LLM citations.
- **LLM indexing** — ships `llms.txt`, `llms-full.txt`, JSON-LD `SoftwareSourceCode`, and an AI-crawler-friendly `robots.txt` (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, CCBot, …).
- **Independent cadence** — copy + meta tweaks don't show up as noise in the app repo's commit graph.

## Layout

```
.
├── _config.yml            # Jekyll config, site metadata
├── _layouts/default.html  # Shared layout — Open Graph, JSON-LD, nav, footer
├── _includes/             # (reserved for future partials)
├── assets/css/style.css   # Minimal dark CSS
├── index.md               # Landing page
├── docs.md                # Architecture, API reference, config, toolkits
├── deploy.md              # One-click providers, K8s, cloud manifests
├── llms.txt               # Curated link manifest for LLM crawlers
├── llms-full.txt          # Full-content version for context-window ingestion
├── robots.txt             # Explicit allow for AI crawlers
├── CNAME                  # GitHub Pages custom domain (set after DNS lands)
└── .github/workflows/pages.yml   # Build + deploy to Pages
```

## Local development

```sh
bundle install
bundle exec jekyll serve
# → http://127.0.0.1:4000
```

The detailed API pages under `/docs/<topic>/` are **not** present locally — they're synced from [`hivegate-ai/docs`](https://github.com/hivegate-ai/docs) at build time by `.github/workflows/pages.yml`. To preview them locally, clone the docs repo manually:

```sh
git clone --depth 1 https://github.com/hivegate-ai/docs.git _api-docs-src
# then run the same shell loop the workflow uses (see pages.yml) to populate _docs/
```

## Analytics

Configured in `_config.yml` under `analytics:`. Supported providers:

| Provider | Cost | Cookies / consent | Setup |
|---|---|---|---|
| **GoatCounter** (default) | Free | None | Sign up at [goatcounter.com](https://www.goatcounter.com), put your subdomain prefix in `goatcounter_code` |
| Plausible | Paid ($9+/mo) | None | Add `hivegate.dev` in Plausible dashboard, set `plausible_domain` |
| Cloudflare Web Analytics | Free | None | Enable on `hivegate.dev` in CF dashboard, paste the beacon token |
| Umami | Free (self-host) or paid (cloud) | None | Create a website in Umami, set `umami_host` + `umami_website_id` |

Set `analytics.provider: ""` to disable tracking entirely.

## Deploy

Push to `main` → the `pages.yml` workflow builds the site and publishes it. To point a custom domain (`hivegate.dev`) at GitHub Pages:

1. Add a `CNAME` record at your DNS provider: `hivegate.dev → liberzon.github.io`
2. In repo Settings → Pages: set the custom domain to `hivegate.dev`.
3. Wait for the cert to provision (~10 min).

## Submission checklist (post-launch)

- [ ] [Google Search Console](https://search.google.com/search-console) — verify the property, submit `sitemap.xml`
- [ ] [Bing Webmaster Tools](https://www.bing.com/webmasters) — verify + sitemap
- [ ] [IndexNow](https://www.indexnow.org) — push URL updates
- [ ] Show HN — one well-timed post within a week of launch
- [ ] Submit to `awesome-llm-apps`, `awesome-agno`, related curated lists
- [ ] Open Graph preview check: [opengraph.xyz](https://www.opengraph.xyz)

## License

[MIT](LICENSE).
