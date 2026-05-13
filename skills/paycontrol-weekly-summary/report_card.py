#!/usr/bin/env python3
"""Generate a hybrid report card PNG.

Usage:
    report_card.py <out_path> <data_json_path>

data_json keys:
  date, stats{merged,tracked,untracked,stale_issues},
  shipped_tracked[{number,title,theme}], shipped_untracked[{number,title,author}],
  closed_by_area[{area,issues[{number,title}]}],
  stale[{number,title,days,assignee}],
  action_items[{level,title,detail}],
  contributors[{name,total,tracked,untracked}],
  board_drift[{pr,issue,title}]
"""
import json, sys, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

out_path = sys.argv[1]
data = json.load(open(sys.argv[2]))

TEAL   = "#1B8F8F"
ORANGE = "#E07B2A"
PURPLE = "#7B3F9E"
RED    = "#C0392B"
YELLOW_BG = "#FFFBEA"
YELLOW_BORDER = "#F0C040"
GRAY   = "#5A6370"
LGRAY  = "#E8EAED"
BLACK  = "#1A1A2E"
WHITE  = "#FFFFFF"
GREEN  = "#2ECC71"

fig = plt.figure(figsize=(11, 17), facecolor=WHITE)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 11)
ax.set_ylim(0, 17)
ax.axis("off")

def card(x, y, w, h, color=WHITE, border=LGRAY, radius=0.18, lw=1.0):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle=f"round,pad=0.0,rounding_size={radius}",
                       facecolor=color, edgecolor=border, linewidth=lw,
                       transform=ax.transData, clip_on=False)
    ax.add_patch(p)

def label(x, y, text, size=7, color=GRAY, weight="normal", ha="left", va="top"):
    ax.text(x, y, text, fontsize=size, color=color, fontweight=weight,
            ha=ha, va=va, transform=ax.transData)

def section_header(x, y, text, color=GRAY):
    ax.text(x, y, text.upper(), fontsize=6.5, color=color, fontweight="bold",
            ha="left", va="top", transform=ax.transData,
            fontfamily="monospace")

def bullet(ax, x, y, text, color=BLACK, size=7.5, indent=0.18, max_width=45):
    ax.text(x, y, "•", fontsize=7, color=GRAY, ha="left", va="top", transform=ax.transData)
    lines = textwrap.wrap(text, max_width)
    for i, line in enumerate(lines):
        ax.text(x + indent, y - i * 0.21, line, fontsize=size, color=color,
                ha="left", va="top", transform=ax.transData)
    return len(lines)

# ── Outer card ───────────────────────────────────────────────────────────────
card(0.25, 0.25, 10.5, 16.5, border="#C8CDD4", radius=0.3, lw=1.2)

# ── Title ────────────────────────────────────────────────────────────────────
label(0.6, 16.45, "PayControl — Hybrid Weekly Report", size=13, color=BLACK, weight="bold")
label(0.6, 16.05, f"PayControlLimited/PayControl  ·  {data['date']}", size=8, color=GRAY)

ax.axhline(y=15.75, xmin=0.05, xmax=0.95, color=LGRAY, linewidth=1)

# ── Stat boxes ───────────────────────────────────────────────────────────────
s = data["stats"]
stats = [
    (str(s["merged"]),      "PRs Merged",      TEAL),
    (f"{s['tracked']}",     "Tracked",         TEAL),
    (f"{s['untracked']}",   "Untracked",       ORANGE),
    (str(s["stale_issues"]), "Stale Issues",   RED),
]
sw = 2.35
for i, (val, lbl, col) in enumerate(stats):
    bx = 0.45 + i * (sw + 0.14)
    card(bx, 14.8, sw, 0.82, border=LGRAY)
    ax.text(bx + sw/2, 15.44, val, fontsize=20, color=col, fontweight="bold",
            ha="center", va="top", transform=ax.transData)
    ax.text(bx + sw/2, 14.96, lbl, fontsize=7.5, color=GRAY,
            ha="center", va="bottom", transform=ax.transData)

ax.axhline(y=14.65, xmin=0.05, xmax=0.95, color=LGRAY, linewidth=0.8)

# ── Action Items ─────────────────────────────────────────────────────────────
cy = 14.42
label(0.6, cy, "[ ! ]  Action Items", size=9.5, color=BLACK, weight="bold")
cy -= 0.32

for item in data["action_items"][:4]:
    dot_color = RED if item["level"] == "red" else ORANGE
    ax.text(0.68, cy, "●", fontsize=7, color=dot_color, ha="left", va="top", transform=ax.transData)
    title_text = f"{item['title']} — {item['detail']}"
    lines = textwrap.wrap(title_text, 90)
    for j, line in enumerate(lines):
        ax.text(0.88, cy - j*0.21, line, fontsize=7.5, color=BLACK,
                ha="left", va="top", transform=ax.transData)
    cy -= 0.22 * max(len(lines), 1) + 0.08

ax.axhline(y=cy - 0.05, xmin=0.05, xmax=0.95, color=LGRAY, linewidth=0.8)
cy -= 0.22

# ── What Actually Shipped (left) + What Was Tracked (right) ──────────────────
col_mid = 5.9
shipped_top = cy

label(0.6, cy, "[ > ]  What Actually Shipped", size=9.5, color=BLACK, weight="bold")

cy_l = cy - 0.32
section_header(0.68, cy_l, f"Tracked work  ({len(data['shipped_tracked'])} PRs)")
cy_l -= 0.25
for pr in data["shipped_tracked"][:4]:
    n = bullet(ax, 0.72, cy_l,
               f"#{pr['number']} {pr['title'][:55]}", size=7.5)
    cy_l -= 0.22 * n + 0.07

cy_l -= 0.08
pct_u = round(s['untracked'] / max(s['merged'],1) * 100)
section_header(0.68, cy_l, f"Untracked  ({len(data['shipped_untracked'])} PRs — {pct_u}% of merges)", color=ORANGE)
cy_l -= 0.25
for pr in data["shipped_untracked"][:6]:
    n = bullet(ax, 0.72, cy_l,
               f"#{pr['number']} {pr['title'][:48]} — {pr['author']}", color="#5A3E0A", size=7.5)
    cy_l -= 0.22 * n + 0.07

# Right column — What Was Tracked
label(col_mid + 0.1, shipped_top, "[ = ]  What Was Tracked", size=9.5, color=BLACK, weight="bold")
cy_r = shipped_top - 0.32
for area_block in data["closed_by_area"][:5]:
    section_header(col_mid + 0.18, cy_r, area_block["area"])
    cy_r -= 0.24
    for iss in area_block["issues"][:3]:
        n = bullet(ax, col_mid + 0.22, cy_r,
                   f"#{iss['number']} {iss['title'][:38]}", size=7.5)
        cy_r -= 0.22 * n + 0.06
    cy_r -= 0.06

section_end = min(cy_l, cy_r) - 0.18
ax.axhline(y=section_end, xmin=0.05, xmax=0.95, color=LGRAY, linewidth=0.8)
cy = section_end - 0.22

# ── Warning banner (untracked signal) ────────────────────────────────────────
if pct_u >= 40:
    banner_h = 0.42
    card(0.45, cy - banner_h + 0.1, 10.1, banner_h,
         color=YELLOW_BG, border=YELLOW_BORDER, radius=0.12, lw=1.2)
    ax.text(0.72, cy - 0.04,
            f"⚠  {pct_u}% of merged PRs had no linked issue — {s['untracked']} PRs shipped without board visibility.",
            fontsize=8, color="#7A5000", ha="left", va="top", transform=ax.transData)
    cy -= banner_h + 0.14

# ── Stale Issues ─────────────────────────────────────────────────────────────
label(0.6, cy, "[ ~ ]  Stale Issues", size=9.5, color=BLACK, weight="bold")
stale_count = data["stats"]["stale_issues"]
label(8.5, cy, f"{stale_count} total", size=8, color=RED, weight="bold", ha="left")
cy -= 0.28

# Mini table header
for x_pos, hdr in [(0.68, "Age"), (1.35, "Issue"), (8.35, "Owner")]:
    ax.text(x_pos, cy, hdr, fontsize=6.5, color=GRAY, fontweight="bold",
            ha="left", va="top", transform=ax.transData)
cy -= 0.05
ax.axhline(y=cy, xmin=0.06, xmax=0.94, color=LGRAY, linewidth=0.7)
cy -= 0.2

for i, s_iss in enumerate(data["stale"][:6]):
    row_col = "#F9F9F9" if i % 2 == 0 else WHITE
    card(0.45, cy - 0.17, 10.1, 0.22, color=row_col, border=row_col, radius=0.05, lw=0)
    ax.text(0.68, cy, f"{s_iss['days']}d", fontsize=7.5, color=RED,
            fontweight="bold", ha="left", va="top", transform=ax.transData)
    title_trunc = s_iss["title"][:62]
    ax.text(1.35, cy, f"#{s_iss['number']}  {title_trunc}", fontsize=7.5, color=BLACK,
            ha="left", va="top", transform=ax.transData)
    ax.text(8.35, cy, s_iss.get("assignee", "—"), fontsize=7.5, color=GRAY,
            ha="left", va="top", transform=ax.transData)
    cy -= 0.25

ax.axhline(y=cy - 0.04, xmin=0.05, xmax=0.95, color=LGRAY, linewidth=0.8)
cy -= 0.26

# ── Board drift ───────────────────────────────────────────────────────────────
if data.get("board_drift"):
    label(0.6, cy, "[ ? ]  Board Drift", size=9.5, color=BLACK, weight="bold")
    cy -= 0.27
    for d in data["board_drift"][:3]:
        n = bullet(ax, 0.72, cy,
                   f"PR #{d['pr']} merged → issue #{d['issue']} still open: {d['title'][:55]}",
                   color=PURPLE, size=7.5)
        cy -= 0.22 * n + 0.07
    ax.axhline(y=cy - 0.06, xmin=0.05, xmax=0.95, color=LGRAY, linewidth=0.8)
    cy -= 0.26

# ── Contributors ─────────────────────────────────────────────────────────────
label(0.6, cy, "[ + ]  Contributors", size=9.5, color=BLACK, weight="bold")
cy -= 0.32

contribs = data["contributors"]
cols = 2
cw = 4.8
ch = 0.85
for i, c in enumerate(contribs[:6]):
    cx = 0.45 + (i % cols) * (cw + 0.26)
    cy_c = cy - (i // cols) * (ch + 0.12)
    card(cx, cy_c - ch + 0.08, cw, ch, border=LGRAY, radius=0.14)
    ax.text(cx + 0.22, cy_c - 0.06, c["name"], fontsize=9, color=BLACK,
            fontweight="bold", ha="left", va="top", transform=ax.transData)
    ax.text(cx + 0.22, cy_c - 0.32,
            f"{c['total']} merged  ·  {c['tracked']} tracked / {c['untracked']} untracked",
            fontsize=7.5, color=GRAY, ha="left", va="top", transform=ax.transData)
    # mini bar
    bar_w = cw - 0.44
    bar_h = 0.13
    bar_y = cy_c - ch + 0.22
    ax.add_patch(mpatches.Rectangle((cx + 0.22, bar_y), bar_w, bar_h,
                                    color=ORANGE, transform=ax.transData))
    if c["total"] > 0:
        tracked_w = bar_w * c["tracked"] / c["total"]
        ax.add_patch(mpatches.Rectangle((cx + 0.22, bar_y), tracked_w, bar_h,
                                        color=TEAL, transform=ax.transData))
    ax.text(cx + 0.22, bar_y - 0.07, "teal = tracked", fontsize=5.5,
            color=TEAL, ha="left", va="top", transform=ax.transData)
    ax.text(cx + cw - 0.22, bar_y - 0.07, "orange = untracked", fontsize=5.5,
            color=ORANGE, ha="right", va="top", transform=ax.transData)

plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=WHITE)
print(out_path)
