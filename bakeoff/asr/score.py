# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["sherpa-onnx>=1.12", "numpy", "soundfile", "soxr"]
# ///
"""Transcribes every segment an engine produced with SenseVoice and reports CER.

A segment whose CER exceeds BAD_CER is what the real pipeline would regenerate,
so the share of such segments estimates each engine's retry rate.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import sherpa_onnx
import soundfile as sf
import soxr

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"
BAD_CER = 0.10
ASR_SR = 16000


def recognizer():
    return sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=str(MODEL / "model.int8.onnx"), tokens=str(MODEL / "tokens.txt"),
        language="zh", use_itn=True, num_threads=4)


_DIGITS = "零一二三四五六七八九"


def _cn_int(n):
    """Reads a non-negative integer below 10^8 the way it is spoken: 11 -> 十一, 1280 -> 一千二百八十."""
    if n < 10:
        return _DIGITS[n]
    if n < 20:
        return "十" + (_DIGITS[n % 10] if n % 10 else "")
    if n >= 10000:
        hi, lo = divmod(n, 10000)
        return _cn_int(hi) + "万" + (("零" if lo < 1000 else "") + _cn_int(lo) if lo else "")
    out, zero = "", False
    for unit, v in (("千", 1000), ("百", 100), ("十", 10), ("", 1)):
        d, n = divmod(n, v)
        if d:
            out += ("零" if zero and out else "") + _DIGITS[d] + unit
            zero = False
        elif out:
            zero = True
    return out


def _numbers_to_cn(s):
    """ASR's inverse text normalization writes digits where the source text has Chinese numerals."""
    s = re.sub(r"(\d{4})(?=年)", lambda m: "".join(_DIGITS[int(c)] for c in m.group(1)), s)
    s = re.sub(r"(\d+)\.(\d+)", lambda m: _cn_int(int(m.group(1))) + "点" + "".join(_DIGITS[int(c)] for c in m.group(2)), s)
    return re.sub(r"\d+", lambda m: _cn_int(int(m.group())), s)


def normalize(s):
    s = unicodedata.normalize("NFKC", s).lower()
    s = s.replace(",", "")  # thousands separators
    s = _numbers_to_cn(s)
    s = re.sub("[的得地]", "的", s)  # homophones the ASR cannot tell apart
    return "".join(ch for ch in s if not unicodedata.category(ch).startswith(("P", "Z", "S")))


def cer(ref, hyp):
    ref, hyp = normalize(ref), normalize(hyp)
    if not ref:
        return 0.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)


def score(engine_dir, rec):
    metrics = json.loads((engine_dir / "metrics.json").read_text(encoding="utf-8"))
    report = {"engine": metrics["engine"], "items": {}}
    errs = chars = bad = total = 0
    for item_id, item in metrics["items"].items():
        rows = []
        for seg in item["segments"]:
            audio, sr = sf.read(engine_dir / "segments" / f"{item_id}_{seg['n']:03d}.wav", dtype="float32")
            if sr != ASR_SR:
                audio = soxr.resample(audio, sr, ASR_SR)
            stream = rec.create_stream()
            stream.accept_waveform(ASR_SR, audio)
            rec.decode_stream(stream)
            hyp = re.sub(r"<\|[^|]*\|>", "", stream.result.text)
            c = cer(seg["text"], hyp)
            n = len(normalize(seg["text"]))
            errs += c * n
            chars += n
            total += 1
            bad += c > BAD_CER
            rows.append({"n": seg["n"], "cer": round(c, 3), "ref": seg["text"], "hyp": hyp})
        report["items"][item_id] = rows
    report["total"] = {"cer": errs / chars, "bad_segments": bad, "segments": total, "retry_rate": bad / total}
    (engine_dir / "asr.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("engines", nargs="+", help="engine output dirs under out/")
    ap.add_argument("-v", "--verbose", action="store_true", help="print every segment above BAD_CER")
    args = ap.parse_args()
    rec = recognizer()
    for name in args.engines:
        r = score(ROOT / "out" / name, rec)
        t = r["total"]
        print(f"{name}: CER {t['cer']:.2%}, retry {t['bad_segments']}/{t['segments']} ({t['retry_rate']:.0%})")
        if args.verbose:
            for item_id, rows in r["items"].items():
                for row in rows:
                    if row["cer"] > BAD_CER:
                        print(f"  {item_id}#{row['n']} {row['cer']:.0%}\n    ref: {row['ref']}\n    hyp: {row['hyp']}")
    sys.exit(0)
