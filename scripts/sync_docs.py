#!/usr/bin/env python3
"""Turn the hivegate-ai/docs checkout into Jekyll pages under _docs/.

Each page gets the title of its own H1, a description written for search results,
and a last_modified_at date from the docs repo's git history, which jekyll-sitemap
emits as <lastmod>. The site's own pages (index, docs, deploy) get the same date
stamp from this repo's history.

Usage: scripts/sync_docs.py <docs-checkout> <out-dir>
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# Files in hivegate-ai/docs that don't become pages: the all-in-one mega-file, and the
# two index pages, which duplicate the site's own /docs/ page.
SKIP = {"API_DOCUMENTATION", "index", "README"}

# Shown in search results, so each one says what that page covers. A new docs page
# without an entry still builds (with its first paragraph) and logs a warning.
DESCRIPTIONS = {
    "agent-packs": "Provision a complete supervisor/worker team from one YAML pack: the pack.yaml schema, how to apply a pack, and the default supervisor pack.",
    "api-admin": "Admin API reference: create and manage API keys, inspect and reload caches, and list or cancel background tasks, using X-Admin-Secret.",
    "api-agents": "Agents API reference: create, list and delete agents, chat with streamed or JSON replies, use MCP tools, and resume paused runs.",
    "api-approvals": "Approvals API reference: list pending supervisor job approvals, approve or deny them, and list notification plugins.",
    "api-engines": "Engines API reference: register, update and remove the execution engines that supervisor workers run on.",
    "api-knowledge": "Knowledge API reference: create, list, update and delete per-tenant and per-collection knowledge entries for agent retrieval.",
    "api-prompts": "Prompts API reference: create, list, update and delete the versioned prompt templates agents run with, without a redeploy.",
    "api-skills": "Skills API reference: create, list, update and delete reusable skill definitions shared by agents and workers.",
    "api-targets": "Targets API reference: register the execution targets supervisor runs use, and check their health.",
    "api-teams": "Teams API reference: create multi-agent teams, run and resume them, manage members, and read or delete team sessions and memories.",
    "api-tokens": "Tokens API reference: store each user's OAuth tokens, read them with automatic refresh, refresh on demand and delete them.",
    "authentication": "How HiveGate authenticates requests: X-API-Key on /v2 routes, X-Admin-Secret on /admin, open health routes, and local development mode.",
    "configuration": "The environment variables HiveGate reads, required and optional, with what each one controls.",
    "database-schema": "HiveGate's PostgreSQL tables: agents, teams, prompts, knowledge, OAuth tokens, API keys, token usage, and supervisor jobs, engines and targets.",
    "deployment": "Run HiveGate beyond your laptop: Docker Compose for development, a production setup, and the health endpoints to monitor.",
    "development": "Work on HiveGate itself: set up the environment, run validation and tests, apply database migrations and manage dependencies.",
    "llm-models": "Choose the model HiveGate agents run on: the default model, latest-of-a-tier aliases, pinned model ids, provider keys and Claude refusals.",
    "models-reference": "The Pydantic request, response and shared models behind the HiveGate REST API.",
    "overview": "How HiveGate fits together: a FastAPI service on Agno for agents, teams, prompts, knowledge and per-user tokens. Architecture and key concepts.",
    "quickstart": "Run HiveGate locally: clone the repo, configure .env, start Postgres and Qdrant with Docker Compose, and make your first API call.",
    "remote-agent": "Run Claude Code work on remote targets: locally, over SSH, through a remote service, or in Docker and Kubernetes containers.",
    "supervisor-platform": "The supervisor platform: a supervisor agent classifies requests and delegates them to worker agents, with engines, targets, limits and MCP.",
    "toolkits": "HiveGate's agent toolkits: Calendar, Email, Contacts and Drive for Google and Microsoft, Claude Code and managed agents, with approval before writes.",
}

SITE_PAGES = ["index.md", "docs.md", "deploy.md"]


def last_modified(repo: Path, path: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%cI", "--", path],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if not out:
        raise SystemExit(f"No git history for {repo / path}; clone with full history")
    return out


def title_of(slug: str, text: str) -> str:
    match = re.search(r"^# (.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else slug.replace("-", " ").title()


def first_paragraph(text: str) -> str:
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if block and not block.startswith(("#", "|", "`", ">", "-", "*", "<")):
            return " ".join(block.split())[:155]
    return ""


def main(docs: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    for src in sorted(docs.glob("*.md")):
        slug = src.stem
        if slug in SKIP:
            continue
        text = src.read_text(encoding="utf-8")
        description = DESCRIPTIONS.get(slug)
        if description is None:
            description = first_paragraph(text)
            print(f"::warning::No description for docs page '{slug}'; add one to scripts/sync_docs.py")
        front = {
            "layout": "default",
            "title": title_of(slug, text),
            "description": description,
            "permalink": f"/docs/{slug}/",
            "last_modified_at": last_modified(docs, src.name),
        }
        # JSON strings are valid YAML scalars, so this quotes titles safely.
        header = "".join(f"{key}: {json.dumps(value)}\n" for key, value in front.items())
        (out / src.name).write_text(f"---\n{header}---\n\n{text}", encoding="utf-8")
        count += 1
    print(f"Synced {count} detailed doc pages.")

    site = Path(".")
    for name in SITE_PAGES:
        page = site / name
        text = page.read_text(encoding="utf-8")
        if not text.startswith("---\n") or "\nlast_modified_at:" in text.split("\n---", 1)[0]:
            continue
        stamp = json.dumps(last_modified(site, name))
        page.write_text(f"---\nlast_modified_at: {stamp}\n{text[4:]}", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
