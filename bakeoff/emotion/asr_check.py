# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["sherpa-onnx==2.0.0", "numpy", "soundfile", "soxr==1.1.0"]
# ///
"""Reads every comparison clip back with SenseVoice and prints the per-version error rate, so a version that
garbles or speaks its instruction aloud is caught before the blind test."""
import json
import sys
from pathlib import Path

import soundfile as sf
import soxr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "asr"))
import score  # noqa: E402

rec = score.recognizer()
lines = json.loads((HERE / "lines" / "lines.json").read_text(encoding="utf-8"))


def cer(ref, hyp):
    r, h = score.normalize(ref), score.normalize(hyp)
    prev = list(range(len(h) + 1))
    for i, a in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, b in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a != b))
        prev = cur
    return prev[-1] / max(len(r), 1)


for d in sorted(p for p in (HERE / "lines").iterdir() if p.is_dir()):
    errs = []
    for k, line in enumerate(lines):
        wav = d / f"{k:02d}.wav"
        if not wav.exists():
            continue
        a, sr = sf.read(wav, dtype="float32")
        s = rec.create_stream()
        s.accept_waveform(16000, soxr.resample(a, sr, 16000))
        rec.decode_stream(s)
        errs.append(cer(line["line"], s.result.text))
        if errs[-1] > 0.3:
            print(f"  {d.name} {k:02d}: {line['line']} -> {s.result.text}")
    print(f"{d.name:14} {len(errs)} clips, error {sum(errs) / len(errs) * 100:.1f}%")
