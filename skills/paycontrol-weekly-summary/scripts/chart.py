#!/usr/bin/env python3
"""Generate the weekly chart PNG.

Usage:
    chart.py <out_path> <iso_date> <issues_total> <ttm_median_h> \
             <issues_by_area_json> <ttm_buckets_json>

Example:
    chart.py out.png 2026-04-28 23 3.5 \
      '[["Backoffice",4],["Enhancement",4]]' \
      '[11,13,10,8,3]'
"""
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

out_path, iso_date, issues_total, ttm_median, issues_json, ttm_json = sys.argv[1:7]
issues = json.loads(issues_json)
ttm_buckets = json.loads(ttm_json)

DEFAULT_COLORS = [
    "#a53e91", "#a2eeef", "#c522c6", "#d73a4a", "#78e341",
    "#c3c4b4", "#888888", "#6a737d", "#0075ca", "#43e382",
]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.5))

labels = [x[0] for x in issues]
counts = [x[1] for x in issues]
colors = (DEFAULT_COLORS * ((len(labels) // len(DEFAULT_COLORS)) + 1))[: len(labels)]
ax1.barh(labels[::-1], counts[::-1], color=colors[::-1])
ax1.set_title(f"Issues opened by area ({issues_total} total)", fontsize=12, fontweight="bold")
ax1.set_xlabel("count")
for i, c in enumerate(counts[::-1]):
    ax1.text(c + 0.05, i, str(c), va="center", fontsize=9)
ax1.spines["top"].set_visible(False)
ax1.spines["right"].set_visible(False)

bucket_labels = ["<1h", "1-4h", "4-24h", "1-3d", ">3d"]
bucket_colors = ["#28a745", "#85c97e", "#f1c40f", "#fd7e14", "#d73a4a"]
bars = ax2.bar(bucket_labels, ttm_buckets, color=bucket_colors)
ax2.set_title(f"PR time-to-merge (median {ttm_median}h)", fontsize=12, fontweight="bold")
ax2.set_ylabel("PR count")
for bar, v in zip(bars, ttm_buckets):
    ax2.text(bar.get_x() + bar.get_width() / 2, v + 0.2, str(v),
             ha="center", fontsize=10, fontweight="bold")
ax2.spines["top"].set_visible(False)
ax2.spines["right"].set_visible(False)

plt.suptitle(f"PayControl Weekly - {iso_date}", fontsize=14, fontweight="bold", y=1.02)
plt.tight_layout()
plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
print(out_path)
