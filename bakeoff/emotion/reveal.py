"""Reveals the emotion blind test: python3 reveal.py ~/Downloads/emotion_scores.json -> emotion/RESULTS.md"""
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
mapping = json.loads((HERE / "mapping.json").read_text(encoding="utf-8"))
scores = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
total, best = defaultdict(list), defaultdict(int)
for k, s in scores["lines"].items():
    order = mapping[k]
    for i, v in enumerate(s["scores"]):
        if v:
            total[order[i]].append(v)
    if s.get("best") is not None:
        best[order[s["best"]]] += 1
rows = ["| 做法 | 平均分 (1–5) | 评了几句 | 被选为最好 |", "|---|---|---|---|"]
for e in sorted(total, key=lambda e: -sum(total[e]) / len(total[e])):
    rows.append(f"| `{e}` | {sum(total[e]) / len(total[e]):.2f} | {len(total[e])} | {best[e]} |")
notes = scores.get("notes", "").strip()
(HERE / "RESULTS.md").write_text("# 情绪对白盲听结果\n\n" + "\n".join(rows) + (f"\n\n## 备注\n\n{notes}\n" if notes else "\n"),
                                 encoding="utf-8")
print("\n".join(rows))
