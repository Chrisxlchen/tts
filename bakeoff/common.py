"""Shared harness for the TTS bake-off.

Every engine runner only supplies `synth(text) -> (float32 mono array, sample_rate)`;
this module handles texts, segmentation, timing and output layout so engines are comparable.

Output layout: out/<engine>/<item_id>.wav, out/<engine>/segments/<item_id>_<n>.wav,
out/<engine>/metrics.json.
"""
import argparse
import csv
import json
import re
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent
TEXTS = ROOT / "texts"
OUT = ROOT / "out"

SENTENCE_GAP_S = 0.25
PARAGRAPH_GAP_S = 0.6
MAX_SEGMENT_CHARS = 60


def load_items():
    """Returns [(item_id, [paragraph, ...])]: the short test cases, then the long passage."""
    items = []
    with open(TEXTS / "cases.tsv", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            items.append((row["id"], [row["text"].strip()]))
    paragraphs = [p.strip() for p in (TEXTS / "passage.txt").read_text(encoding="utf-8").split("\n") if p.strip()]
    items.append(("passage", paragraphs))
    return items


_SENTENCE_END = re.compile(r"(?<=[。！？；…])(?![”」』）])|(?<=[。！？…][”」』）])")


def split_paragraph(paragraph):
    """Splits a paragraph into Segments: whole sentences, merged while they stay short."""
    sentences = [s for s in _SENTENCE_END.split(paragraph) if s.strip()]
    segments = []
    for s in sentences:
        if segments and len(segments[-1]) + len(s) <= MAX_SEGMENT_CHARS:
            segments[-1] += s
        else:
            segments.append(s)
    return segments


def _resample_check(sr, expected):
    if expected is not None and sr != expected:
        raise ValueError(f"engine changed sample rate mid-run: {sr} vs {expected}")


def run(engine, synth, only=None, warmup_text="你好，这是一段预热语音。"):
    """Synthesizes every item with `synth`, recording generation time vs audio duration."""
    out_dir = OUT / engine
    seg_dir = out_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)

    synth(warmup_text)  # model load and graph compilation should not count towards speed

    metrics = {"engine": engine, "items": {}}
    sr_seen = None
    for item_id, paragraphs in load_items():
        if only and item_id not in only:
            continue
        pieces, segments = [], []
        gen_s = 0.0
        n = 0
        for p_idx, paragraph in enumerate(paragraphs):
            for s_idx, text in enumerate(split_paragraph(paragraph)):
                t0 = time.perf_counter()
                audio, sr = synth(text)
                dt = time.perf_counter() - t0
                _resample_check(sr, sr_seen)
                sr_seen = sr
                audio = np.asarray(audio, dtype=np.float32).reshape(-1)
                gen_s += dt
                seg_path = seg_dir / f"{item_id}_{n:03d}.wav"
                sf.write(seg_path, audio, sr)
                segments.append({"n": n, "text": text, "gen_s": dt, "audio_s": len(audio) / sr})
                if pieces:
                    gap = SENTENCE_GAP_S if s_idx else PARAGRAPH_GAP_S
                    pieces.append(np.zeros(int(gap * sr), dtype=np.float32))
                pieces.append(audio)
                n += 1
                print(f"[{engine}] {item_id} #{n} {len(audio)/sr:5.1f}s audio in {dt:5.2f}s", flush=True)
        full = np.concatenate(pieces)
        sf.write(out_dir / f"{item_id}.wav", full, sr_seen)
        audio_s = sum(s["audio_s"] for s in segments)
        metrics["items"][item_id] = {"gen_s": gen_s, "audio_s": audio_s, "rtf": gen_s / audio_s, "segments": segments}

    total_gen = sum(i["gen_s"] for i in metrics["items"].values())
    total_audio = sum(i["audio_s"] for i in metrics["items"].values())
    metrics["total"] = {"gen_s": total_gen, "audio_s": total_audio, "rtf": total_gen / total_audio,
                        "x_realtime": total_audio / total_gen, "sample_rate": sr_seen}
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{engine}] total {total_audio:.0f}s audio in {total_gen:.0f}s -> {total_audio/total_gen:.2f}x realtime")
    return metrics


def cli(description):
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--only", nargs="*", help="item ids to synthesize (default: all)")
    return ap
