"""Builds the emotion blind test (python3 blind.py [version dir ...], default every version): emotion/session/情绪盲听.html, one self-contained page.

Every line's versions are shuffled separately and labelled 1..n; the order goes to emotion/mapping.json,
which the page never sees. Audio is embedded as AAC so the page also works when sent to a phone.
"""
import base64
import json
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LINES = HERE / "lines"
ENGINES = sys.argv[1:] or [d.name for d in sorted(LINES.iterdir()) if d.is_dir()]  # versions to compare


def aac(wav):
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "64k", "-f", "adts", "-"],
                         check=True, capture_output=True).stdout
    return "data:audio/aac;base64," + base64.b64encode(out).decode()


lines = json.loads((LINES / "lines.json").read_text(encoding="utf-8"))
rng = random.Random()
items, mapping = [], {}
for k, line in enumerate(lines):
    engines = [e for e in ENGINES if (LINES / e / f"{k:02d}.wav").exists()]
    order = rng.sample(engines, len(engines))
    mapping[str(k)] = order
    items.append({"speaker": line["speaker"], "line": line["line"], "emotion": line["emotion"],
                  "direction": line["direction"], "context": line["context"],
                  "clips": [aac(LINES / e / f"{k:02d}.wav") for e in order]})
(HERE / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
page = ((HERE / "template.html").read_text(encoding="utf-8").replace("/*DATA*/null", json.dumps(items, ensure_ascii=False))
    .replace('/*SESSION*/""', json.dumps("".join(map(str, rng.sample(range(10), 6))))))  # fresh scores per session
(HERE / "session").mkdir(exist_ok=True)
out = HERE / "session" / "情绪盲听.html"
out.write_text(page, encoding="utf-8")
print(f"{len(items)} lines x {len(ENGINES)} versions -> {out}")
