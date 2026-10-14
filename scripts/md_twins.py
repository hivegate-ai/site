#!/usr/bin/env python3
"""Publish a plain-markdown copy of each content page next to its HTML, for LLM readers.

/docs/quickstart/ gets /docs/quickstart.md, /blog/<slug>/ gets /blog/<slug>.md, following the
llms.txt convention of "same URL + .md". Run after `jekyll build`; writes into the built site.
The landing page and the blog index are HTML/Liquid layouts, so llms.txt stands in for them.

Usage: scripts/md_twins.py <site-dir>
"""

import re
import sys
from pathlib import Path

PAGES = ["docs.md", "deploy.md"]
FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
LIQUID = re.compile(r"^.*\{%.*?%\}.*\n?", re.MULTILINE)


def field(front: str, key: str) -> str | None:
    match = re.search(rf"^{key}:\s*(.+)$", front, re.MULTILINE)
    return match.group(1).strip().strip('"') if match else None


def twin(src: Path, url: str, out: Path) -> None:
    text = src.read_text(encoding="utf-8")
    match = FRONT.match(text)
    front, body = (match.group(1), text[match.end():]) if match else ("", text)
    body = LIQUID.sub("", body).strip()
    title, description = field(front, "title"), field(front, "description")
    if body.startswith("# "):
        h1, _, body = body.partition("\n")
    else:
        h1 = f"# {title}" if title else ""
    intro = [h1] if h1 else []
    if description:
        intro.append(f"> {description}")
    intro.append(f"Source: https://hivegate.dev{url}")
    dest = out / (url.strip("/") + ".md")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n\n".join(intro) + "\n\n" + body.strip() + "\n", encoding="utf-8")


def main(out: Path) -> None:
    count = 0
    for name in PAGES:
        front = FRONT.match(Path(name).read_text(encoding="utf-8")).group(1)
        twin(Path(name), field(front, "permalink"), out)
        count += 1
    for src in sorted(Path("_docs").glob("*.md")):
        front = FRONT.match(src.read_text(encoding="utf-8")).group(1)
        twin(src, field(front, "permalink"), out)
        count += 1
    for src in sorted(Path("_posts").glob("*.md")):
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", src.stem)
        twin(src, f"/blog/{slug}/", out)
        count += 1
    print(f"Wrote {count} markdown twins into {out}.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
