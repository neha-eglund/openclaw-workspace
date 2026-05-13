#!/usr/bin/env python3
"""Convert standard Markdown to Slack mrkdwn.

Reads from a file argument or stdin, writes to stdout.
Handles: headers, bold, italic-via-underscores, links, horizontal rules,
strikethrough. Leaves tables alone (prints a stderr warning) since
flattening needs human judgment.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def convert(md: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    lines = md.splitlines()
    out: list[str] = []
    in_code = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Toggle code fence; pass code blocks through verbatim.
        if stripped.startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        if in_code:
            out.append(line)
            continue

        # Tables: leave alone, warn once.
        if "|" in line and re.match(r"^\s*\|?.*\|.*\|?\s*$", line) and "---" not in line:
            if "tables" not in warnings:
                warnings.append("tables")
            out.append(line)
            continue
        # Skip table separator rows like |---|---|
        if re.match(r"^\s*\|?[\s\-:|]+\|[\s\-:|]+\|?\s*$", line):
            out.append(line)
            continue

        # Headers: # Foo -> *Foo* + blank line after.
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            text = m.group(2).strip().rstrip("#").strip()
            out.append(f"*{text}*")
            # Ensure blank line after header for visual break.
            if i + 1 < len(lines) and lines[i + 1].strip() != "":
                out.append("")
            continue

        # Horizontal rules -> blank line.
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            out.append("")
            continue

        converted = line

        # Links: [label](url) -> <url|label>. URL must not contain spaces or `)`.
        converted = re.sub(
            r"\[([^\]]+)\]\(([^)\s]+)\)",
            lambda m: f"<{m.group(2)}|{m.group(1)}>",
            converted,
        )

        # Italic with single * -> single _ . Run BEFORE bold conversion so we
        # don't mangle the asterisks bold conversion will produce. The
        # lookarounds reject **bold** because the inner * sees an adjacent *.
        converted = re.sub(
            r"(?<![\*\w])\*([^*\s][^*\n]*?[^*\s]|[^*\s])\*(?![\*\w])",
            r"_\1_",
            converted,
        )

        # Bold: **text** -> *text*.
        converted = re.sub(r"\*\*([^*\n]+)\*\*", r"*\1*", converted)
        converted = re.sub(r"__([^_\n]+)__", r"*\1*", converted)

        # Strikethrough: ~~text~~ -> ~text~
        converted = re.sub(r"~~([^~\n]+)~~", r"~\1~", converted)

        out.append(converted)

    return "\n".join(out), warnings


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("usage: md_to_slack.py [path-to-markdown]", file=sys.stderr)
        return 2

    if len(argv) == 2:
        path = Path(argv[1])
        if not path.is_file():
            print(f"error: {path} is not a file", file=sys.stderr)
            return 1
        md = path.read_text()
    else:
        md = sys.stdin.read()

    converted, warnings = convert(md)
    sys.stdout.write(converted)
    if not converted.endswith("\n"):
        sys.stdout.write("\n")

    if "tables" in warnings:
        print(
            "warning: pipe tables were left unchanged. Flatten them into bullet "
            "lists manually — see SKILL.md rule 4.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
