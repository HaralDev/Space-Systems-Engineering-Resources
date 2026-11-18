#!/usr/bin/env python3
"""Build the website (docs/index.html) from README.md.

README.md is the single source of truth. This script reads every resource
from it (tables, bullet lists and the "Start here" steps), keeps the level
and format tags, and injects them as JSON into site/template.html.

Usage:
    python3 scripts/build_site.py            # writes docs/index.html
    python3 scripts/build_site.py --fragment out.html
                                             # page without the <html>/<head>
                                             # wrapper, for embedded previews
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = "https://haraldev.github.io/Space-Systems-Engineering-Resources/"

LEVELS = {"🟢": "beginner", "🟡": "intermediate", "🔴": "advanced"}
FORMATS = {"🌐": "browser", "💻": "desktop", "🐍": "python", "📦": "library",
           "📄": "document", "🎥": "video", "💰": "paid"}
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
SKIP_SECTIONS = {"How to read this list", "Contents", "🤝 Contributing"}
# Splits "[name](url) — description" without breaking names that contain " — "
DESC_SPLIT = re.compile(r"(?<=\))(?:\*\*)? — | 💰 — ")


def tags(text):
    level = next((v for k, v in LEVELS.items() if k in text), None)
    formats = [v for k, v in FORMATS.items() if k in text]
    return level, formats


def plain(text):
    text = LINK.sub(lambda m: m.group(1), text)
    text = re.sub(r"\*\*|\*|`", "", text)
    for emoji in list(LEVELS) + list(FORMATS):
        text = text.replace(emoji, "")
    return text.replace("️", "").strip(" —-")


def parse(readme):
    items = []
    group = sub = section = None

    def add(name, url, desc, level, formats, extra=(), topic=None):
        if url.startswith("#") or url.startswith(SITE_URL):
            return  # links into this list or its own website
        desc = plain(desc)
        items.append({
            "name": plain(name), "url": url,
            "desc": desc[:1].upper() + desc[1:],
            "level": level, "formats": formats or ["browser"],
            "extra": [{"name": plain(n), "url": u} for n, u in extra if u != url],
            "group": group,
            "section": "Spacecraft Subsystems" if topic else (sub or group),
            **({"topic": topic} if topic else {}),
        })

    for line in readme.splitlines():
        if m := re.match(r"^## (.*)", line):
            section = m.group(1).strip()
            group = re.sub(r"^\W+", "", section).strip()
            sub = None
            continue
        if m := re.match(r"^### (.*)", line):
            sub = m.group(1).strip()
            continue
        if section is None or section in SKIP_SECTIONS:
            continue

        # "Start here" numbered steps
        if m := re.match(r"^\d+\. (.*)", line):
            body = m.group(1)
            level, formats = tags(body)
            head, _, desc = body.partition(")** — ")
            links = LINK.findall(head + ")")
            if links:
                add(*links[0], desc, level or "beginner", formats)
            continue

        # Bullet lists
        if line.startswith("- "):
            body = line[2:]
            level, formats = tags(body)
            parts = DESC_SPLIT.split(body, maxsplit=1)
            head, desc = parts[0], parts[1] if len(parts) > 1 else ""
            links = LINK.findall(head)
            if not links:
                continue
            if len(links) > 1 and ":" in plain(LINK.sub("", head)):
                # "Gentry Lee on systems engineering: [a] · [b]"
                for name, url in links:
                    add(name, url, head.split(":")[0], level, formats)
            elif len(links) > 1 and " and " in head:
                # "[CelesTrak] and [Space-Track.org] — ..."
                for name, url in links:
                    add(name, url, desc, level, formats)
            else:
                add(*links[0], desc, level, formats, links[1:] + LINK.findall(desc))
            continue

        # Tables
        if line.startswith("|") and not re.match(r"^\|\s*:?-", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells[0] in ("Tool", "Subsystem", "Level"):
                continue
            if len(cells) == 4:  # Tool | What it's for | Format | Level
                links = LINK.findall(cells[0])
                level, _ = tags(cells[3])
                _, formats = tags(cells[2])
                if links:
                    add(*links[0], cells[1], level, formats, LINK.findall(cells[1]))
                else:  # a row that groups several links, e.g. ISS trackers
                    links = LINK.findall(cells[1])
                    add(plain(cells[0]), links[0][1], "Live position of the International Space Station",
                        level, formats, links[1:])
            elif len(cells) == 2:  # Subsystem | resource · resource · ...
                topic = plain(cells[0])
                for piece in cells[1].split(" · "):
                    level, formats = tags(piece)
                    name_part, _, desc = piece.partition(") — ")
                    links = LINK.findall(name_part + ")" if desc else piece)
                    if links:
                        add(*links[0], desc, level, formats, topic=topic)
    return items


def main():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    items = parse(readme)
    template = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
    page = template.replace("/*__DATA__*/[]", json.dumps(items, ensure_ascii=False))

    if len(sys.argv) == 3 and sys.argv[1] == "--fragment":
        Path(sys.argv[2]).write_text(page, encoding="utf-8")
        print(f"{len(items)} resources -> {sys.argv[2]}")
        return

    head, body = page.split("</style>", 1)
    document = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        f"{head}</style>\n</head>\n<body>\n{body.strip()}\n</body>\n</html>\n"
    )
    out = ROOT / "docs" / "index.html"
    out.write_text(document, encoding="utf-8")
    print(f"{len(items)} resources -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
