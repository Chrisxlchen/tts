# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["sherpa-onnx==2.0.0", "numpy", "soundfile", "soxr==1.1.0", "librosa"]
# ///
"""Chooses one designed take per voice type in refs/voices.json and copies it to refs/<name>.wav.

Types marked "locked" (already approved by ear) are left alone.
A take must read its text back cleanly (ASR CER); among those, the one whose median pitch is
closest to the type's target_f0 wins. Pitch only roughly tracks perceived age, so the result
is a starting point for listening, not a verdict.
"""
import json
import shutil
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import soxr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score  # noqa: E402

REFS = Path(__file__).resolve().parents[1] / "refs"


def median_f0(path):
    y, sr = librosa.load(path, sr=16000)
    f0, _, _ = librosa.pyin(y, fmin=70, fmax=500, sr=sr)
    return float(np.nanmedian(f0))


def main():
    rec = score.recognizer()
    library = json.loads((REFS / "voices.json").read_text(encoding="utf-8"))
    for vid, v in library.items():
        if v.get("locked") or "target_f0" not in v or not v["voice"].startswith("ref:"):
            continue
        name = v["voice"][4:]
        takes = sorted(REFS.glob(f"{name}_take*.wav"))
        if not takes:
            print(f"{vid}: no takes")
            continue
        ref = score.normalize((REFS / f"{name}.txt").read_text(encoding="utf-8").strip())
        rows = []
        for t in takes:
            audio, sr = sf.read(t, dtype="float32")
            s = rec.create_stream()
            s.accept_waveform(16000, soxr.resample(audio, sr, 16000))
            rec.decode_stream(s)
            rows.append((score.cer(ref, score.normalize(s.result.text)), median_f0(t), t))
        best_cer = min(r[0] for r in rows)
        chosen = min((r for r in rows if r[0] == best_cer), key=lambda r: abs(r[1] - v["target_f0"]))
        shutil.copy(chosen[2], REFS / f"{name}.wav")
        listing = "  ".join(f"{t.stem[-5:]} {c:.0%} {f:.0f}Hz" for c, f, t in rows)
        print(f"{vid} ({v['label']}, target {v['target_f0']}Hz): {listing}  -> {chosen[2].stem}")


if __name__ == "__main__":
    main()
