"""Un-blinds the listening scores and joins them with speed and ASR metrics into RESULTS.md.

Usage: python3 blind/reveal.py [path/to/scores.json]   (default ~/Downloads/scores.json)
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
NIGHT_H = 8
NEEDED_AUDIO_H = 3.75  # 1.5 h/day of listening at 2.5x


def main():
    scores_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads" / "scores.json"
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    mapping = json.loads((HERE / "mapping.json").read_text(encoding="utf-8"))

    per_letter = defaultdict(list)
    pair_scores = []
    for key, value in scores.items():
        if key in ("notes",) or key.startswith("hour:"):
            continue
        scope, label = key.rsplit(":", 1)
        if scope.startswith("speed_"):
            pair_scores.append((scope, mapping[f"{scope}:{label}"], value))
        else:
            per_letter[label].append(value)

    lines = ["# 盲听结果", "", f"评分文件：`{scores_path}`", "",
             "| 盲听代号 | 引擎 | 平均分 (1–5) | 能听 1 小时？ | 速度 (×实时) | 一晚可生成 | 错字率 | 需重试片段 |",
             "|---|---|---|---|---|---|---|---|"]
    for letter in sorted(l for l in mapping if len(l) == 1):
        engine = mapping[letter]
        m = json.loads((ROOT / "out" / engine / "metrics.json").read_text(encoding="utf-8"))["total"]
        asr_path = ROOT / "out" / engine / "asr.json"
        a = json.loads(asr_path.read_text(encoding="utf-8"))["total"] if asr_path.exists() else None
        vals = per_letter.get(letter, [])
        avg = f"{sum(vals) / len(vals):.2f} ({len(vals)} 条)" if vals else "—"
        night = m["x_realtime"] * NIGHT_H
        night_s = f"{night:.1f} h" + (" ✅" if night >= NEEDED_AUDIO_H else " ❌")
        cer = f"{a['cer']:.1%}" if a else "—"
        retry = f"{a['bad_segments']}/{a['segments']}" if a else "—"
        lines.append(f"| {letter} | `{engine}` | {avg} | {scores.get('hour:' + letter, '—')} | "
                     f"{m['x_realtime']:.2f} | {night_s} | {cer} | {retry} |")
    if pair_scores:
        lines += ["", "## 2.5× 做法对比", "", "| 对比组 | 做法 | 分数 |", "|---|---|---|"]
        lines += [f"| {scope} | {'模型直接 2.5× 合成' if kind == 'native' else '1× 音频加速播放'} | {v} |"
                  for scope, kind, v in sorted(pair_scores)]
    if scores.get("notes"):
        lines += ["", "## 备注", "", scores["notes"]]
    lines += ["", f"一晚按 {NIGHT_H} 小时计算；你每天听 1.5 小时 × 2.5 倍速，需要每晚生成 ≥ {NEEDED_AUDIO_H} 小时音频。",
              "速度为 M3 Pro 实测，Kokoro 为 CPU，Qwen3/VoxCPM2 为 Apple GPU (MLX)，CosyVoice3 为 Apple GPU (PyTorch MPS)。"]
    out = ROOT / "RESULTS.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
