# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["sherpa-onnx==2.0.0", "numpy", "soundfile", "soxr==1.1.0", "librosa"]
# ///
"""Chooses one designed take per voice type in refs/voices.json and copies it to refs/<name>.wav.

Types marked "locked" (already approved by ear) are left alone.
A take must read its text back cleanly (ASR CER). Among those:
- a variant ("variant_of") takes the one that sounds least like the other voices of its type,
  by speaker-embedding cosine similarity, so main characters stay easy to tell apart;
- any other voice takes the one whose median pitch is closest to target_f0.
Pitch only roughly tracks perceived age, so the result is a starting point for listening.
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

ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / "refs"
SPK_MODEL = ROOT / "models" / "spk" / "eres2net_zh.onnx"
AUDITION = ROOT / "out" / "samples" / "voices"  # preset voices are only available as audition clips


class Embedder:
    def __init__(self):
        import sherpa_onnx

        self.x = sherpa_onnx.SpeakerEmbeddingExtractor(
            sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(SPK_MODEL), num_threads=4))

    def __call__(self, path):
        audio, sr = sf.read(path, dtype="float32")
        s = self.x.create_stream()
        s.accept_waveform(16000, soxr.resample(audio, sr, 16000))
        s.input_finished()
        e = np.array(self.x.compute(s))
        return e / np.linalg.norm(e)


def voice_audio(vid, v):
    """A clip of the library voice as currently chosen, or None."""
    if v["voice"].startswith("ref:"):
        path = REFS / f"{v['voice'][4:]}.wav"
    else:
        path = AUDITION / f"{vid}.wav"
    return path if path.exists() else None


def median_f0(path):
    y, sr = librosa.load(path, sr=16000)
    f0, _, _ = librosa.pyin(y, fmin=70, fmax=500, sr=sr)
    return float(np.nanmedian(f0))


def main():
    rec = score.recognizer()
    embed = Embedder()
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
        clean = [r for r in rows if r[0] == best_cer]
        family = v.get("variant_of")
        if family:
            # the type's base voice and the variants chosen before this one
            siblings = [voice_audio(k, o) for k, o in library.items()
                        if k != vid and (k == family or o.get("variant_of") == family)
                        and list(library).index(k) < list(library).index(vid)]
            others = [embed(p) for p in siblings if p]
            closeness = lambda r: max((float(embed(r[2]) @ o) for o in others), default=0.0)  # noqa: E731
            chosen = min(clean, key=closeness)
            note = f"max similarity to its type {closeness(chosen):.2f}"
        else:
            chosen = min(clean, key=lambda r: abs(r[1] - v["target_f0"]))
            note = f"target {v['target_f0']}Hz"
        shutil.copy(chosen[2], REFS / f"{name}.wav")
        listing = "  ".join(f"{t.stem[-5:]} {c:.0%} {f:.0f}Hz" for c, f, t in rows)
        print(f"{vid} ({v['label']}): {listing}  -> {chosen[2].stem} ({note})")


if __name__ == "__main__":
    main()
