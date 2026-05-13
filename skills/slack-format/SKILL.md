---
name: slack-format
description: Convert content to Slack-friendly mrkdwn so it renders cleanly when pasted into Slack. Use when (1) the user asks to "format for Slack", "make this Slack-friendly", or says "this looks bad in Slack"; (2) generating output that the user will copy into Slack (security summaries, weekly reports, status updates, PR digests); (3) converting an existing markdown file to Slack format. Slack does NOT support standard markdown — pound headers render as literal text, double-asterisk bold often renders as literal asterisks, square-bracket parenthesis links render verbatim, and pipe tables become unreadable. Apply Slack's mrkdwn rules instead: single asterisks for bold, underscores for italic, angle-bracket pipe syntax for links, bullet lists in place of tables, blank lines as visual section breaks.
---

# Slack Format

## Overview

Slack uses its own markup called **mrkdwn**. It overlaps with standard Markdown but breaks in important ways. Output written for Slack must follow these rules; standard Markdown pasted into Slack will look broken.

## Quick rules

| Standard Markdown | Slack mrkdwn |
|---|---|
| `**bold**` | `*bold*` (single asterisks) |
| `*italic*` or `_italic_` | `_italic_` only |
| `# Header` | `*Header*` on its own line + blank line |
| `[text](url)` | `<url\|text>` |
| `| col | col |` table | bullet list with bold labels |
| `- item` | `- item` or `• item` (both work) |
| `~~strike~~` | `~strike~` (single tilde) |
| `` `code` `` | `` `code` `` (same) |
| ```` ``` ``` ```` block | ```` ``` ``` ```` (same) |
| `> quote` | `> quote` (same) |
| `---` rule | blank line (no horizontal rule support) |

(Yes, the table above is itself standard Markdown — it's for the human reader of this skill, not for Slack output.)

## Conversion workflow

When asked to convert content for Slack:

1. **Replace headers**: Every `#`, `##`, `###` line becomes a `*bold line*` followed by a blank line. Drop any leading `#` characters.
2. **Replace bold**: `**text**` → `*text*`. Watch out for `***bold italic***` → `*_text_*`.
3. **Replace links**: `[label](https://url)` → `<https://url|label>`. Bare URLs can stay bare.
4. **Kill tables**: Convert any `| ... |` table to a bullet list. Use the first column as a bold label: `- *Row label*: col2 value, col3 value`. For wide tables, one bullet per row with sub-bullets if needed.
5. **Flatten nesting**: Slack supports one level of bullet indentation reliably. Avoid deep nesting; collapse to flat lists with `>` blockquotes or bold prefixes.
6. **Strip horizontal rules**: Replace `---` / `***` / `___` lines with a single blank line.
7. **Preserve code blocks**: Triple-backtick blocks render fine; leave language hints in place even though Slack ignores them.
8. **Keep emojis**: Unicode emoji and `:emoji_name:` shortcodes both render in Slack.

## Special cases

- **Mentions**: `@user` won't ping anyone; the user must add the proper `<@U123456>` ID after pasting. Note this in a footer if relevant.
- **Channel links**: Same — `#channel` is literal text. Use `<#C123456|channel>` only if the channel ID is known.
- **Long messages**: Slack has a 4000-character limit per message and shows a "Show more" cut at ~50 lines. For long reports, suggest the user post the first section and put the rest in a thread.
- **Numbered lists**: Slack auto-numbers `1.` `2.` `3.` lines. If precise numbering matters (e.g. ranked action items), prefix manually: `*1.* Item one`.
- **Trailing whitespace**: Slack collapses multiple blank lines to one — don't rely on extra spacing for layout.
- **Webhook / API posting** (not paste): If the content goes through Slack's `chat.postMessage` API, prefer the [Block Kit](https://api.slack.com/block-kit) JSON format instead of mrkdwn for anything structured. mrkdwn is for paste-into-the-composer use.

## Example: before and after

**Standard Markdown (looks bad in Slack):**

```markdown
# Nightly Security Summary

## Action Items

| Priority | Issue | Owner |
|----------|-------|-------|
| P0       | SQL injection in /search | @neha |
| P1       | Outdated jackson-databind | unassigned |

See [full report](https://github.com/example/repo/issues/42).

**Total findings**: 12
```

**Slack mrkdwn (renders cleanly):**

```
*Nightly Security Summary*

*Action Items*
- *P0*: SQL injection in /search — owner: @neha
- *P1*: Outdated jackson-databind — unassigned

See <https://github.com/example/repo/issues/42|full report>.

*Total findings*: 12
```

## Conversion script

For one-shot conversion of an existing markdown file, use `scripts/md_to_slack.py`:

```bash
python3 scripts/md_to_slack.py path/to/report.md
# or pipe:
cat report.md | python3 scripts/md_to_slack.py
```

The script handles headers, bold, links, horizontal rules, and strikethrough. It does **not** convert tables — those need judgment to flatten well, so the script leaves tables intact and prints a warning. Convert tables manually using rule 4 above.

## When NOT to use this skill

- Content that will be posted via Slack's Block Kit API (use Block Kit JSON instead).
- Content for other chat platforms — Discord and WhatsApp have their own quirks (see workspace `AGENTS.md` for those).
- The Slack message will be short enough that bold/italic don't matter.
