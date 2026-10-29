# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["mlx-audio==0.6.2", "mlx-lm>=0.28", "sherpa-onnx==2.0.0", "soxr==1.1.0", "ebooklib",
#                 "beautifulsoup4", "numpy", "soundfile", "pypinyin"]
# ///
"""Turns a DRM-free EPUB (or a .txt with 第X章 headings) into an audiobook for BookPlayer.

  uv run --script audiobook.py build BOOK.epub [--chapters 1-5]   ingest, cast, act, render, export
  uv run --script audiobook.py cast BOOK.epub [--chapters 1-5]    stop after casting, to review cast.json
  uv run --script audiobook.py list BOOK.epub                     show the Chapters and their numbers

Everything for a book lives in work/<file name>/: book.json, cast.json, speakers/, emotions/, acted/
(IndexTTS-2 takes of charged dialogue, see acting.py), seg/ (cached takes), chapters/NNN <title>.m4a, report.json and <title>.m4b. Re-running skips finished work.
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import acting  # noqa: E402
import casting  # noqa: E402
import export  # noqa: E402
import ingest  # noqa: E402

WORK = HERE / "work"


def chapter_range(spec, count):
    """'3' or '2-5' (1-based, inclusive) -> 0-based indices; None means every Chapter."""
    if not spec:
        return list(range(count))
    lo, _, hi = spec.partition("-")
    return list(range(int(lo) - 1, min(int(hi or lo), count)))


def load(source):
    source = Path(source)
    book_dir = WORK / source.stem
    book_dir.mkdir(parents=True, exist_ok=True)
    book_json = book_dir / "book.json"
    if not book_json.exists():
        book, cover = ingest.ingest(source)
        book_json.write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf-8")
        if cover:
            (book_dir / "cover.jpg").write_bytes(cover)
    return book_dir, json.loads(book_json.read_text(encoding="utf-8"))


def safe(name):
    return "".join(c for c in name if c not in '/\\:*?"<>|')[:40]


def build(book_dir, book, ids, act=True):
    import gc
    import subprocess

    import mlx.core as mx
    import soundfile as sf

    cast = casting.run(book_dir, book, ids)
    gc.collect()
    mx.clear_cache()  # the LLM is done; free its memory before loading the TTS models
    if act:
        acting.tag(book_dir, book, ids)
        gc.collect()
        mx.clear_cache()
        try:
            acting.act(book_dir, book, cast, ids)  # IndexTTS-2 runs in its own process, before the TTS models load
        except (OSError, subprocess.CalledProcessError) as e:
            print(f"[act] IndexTTS-2 failed ({e}); charged lines keep the steady voice", flush=True)

    import synth

    renderer = synth.Renderer(book_dir, cast)
    out_dir = book_dir / "chapters"
    out_dir.mkdir(exist_ok=True)
    report_path = book_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    for n in ids:
        chapter = book["chapters"][n]
        m4a = out_dir / f"{n + 1:03d} {safe(chapter['title'])}.m4a"
        if m4a.exists():
            continue
        speakers = json.loads((book_dir / "speakers" / f"{n:03d}.json").read_text(encoding="utf-8"))
        t0 = time.perf_counter()
        audio, sr, rep = renderer.chapter(chapter, speakers, acting.moods(book_dir, n))
        wav = book_dir / "chapter.tmp.wav"
        sf.write(wav, audio, sr)
        export.chapter_file(wav, m4a, book, n, chapter["title"])
        wav.unlink()
        wall = time.perf_counter() - t0
        report[str(n)] = {k: rep[k] for k in ("title", "audio_s", "gen_s", "retried", "still_bad")} | {"wall_s": wall}
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[audio] {n + 1:03d} {chapter['title']}: {rep['audio_s'] / 60:.1f} min audio in {wall / 60:.1f} min "
              f"({rep['audio_s'] / wall:.2f}x), retried {rep['retried']}, still bad {len(rep['still_bad'])}",
              flush=True)

    done = sorted(out_dir.glob("*.m4a"))
    if len(done) == len(book["chapters"]):
        cover = book_dir / "cover.jpg"
        out = book_dir / f"{safe(book['title'])}.m4b"
        export.m4b([(p, book["chapters"][int(p.name[:3]) - 1]["title"]) for p in done], out, book,
                   cover if cover.exists() else None)
        print(f"[m4b] {out}")
    else:
        print(f"[m4b] {len(done)}/{len(book['chapters'])} chapters rendered; chapters/ can already go to BookPlayer")


def status(book_dir, book):
    """A checklist of every Chapter: rendered or not, whether a build is running, and an ETA."""
    import subprocess

    out_dir = book_dir / "chapters"
    done = {int(p.name[:3]) - 1 for p in out_dir.glob("*.m4a")} if out_dir.exists() else set()
    report_path = book_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    for n, c in enumerate(book["chapters"]):
        r = report.get(str(n))
        info = f"  {r['audio_s'] / 60:4.1f} 分钟" if n in done and r else ""
        print(f"[{'x' if n in done else ' '}] {n + 1:03d} {c['title']}{info}")
    timed = [report[str(n)] for n in done if str(n) in report and report[str(n)]["gen_s"] > 60]
    chars_left = sum(len(p) for n, c in enumerate(book["chapters"]) if n not in done for p in c["paragraphs"])
    running = subprocess.run(["pgrep", "-f", f"audiobook.py build .*{book_dir.name}"], capture_output=True).returncode == 0
    print(f"\n完成 {len(done)}/{len(book['chapters'])} 章，"
          f"已合成 {sum(report[str(n)]['audio_s'] for n in done if str(n) in report) / 3600:.1f} 小时音频；"
          f"合成进程{'正在运行' if running else '没有运行'}")
    if timed and chars_left:
        chars = {n: sum(len(p) for p in book["chapters"][n]["paragraphs"]) for n in done}
        per_char = sum(r["wall_s"] for r in timed) / sum(chars[int(n)] for n, r in report.items()
                                                          if int(n) in done and r in timed)
        print(f"剩余约 {chars_left * per_char / 3600:.1f} 小时（Mac 保持唤醒时）")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["build", "cast", "list", "status"])
    ap.add_argument("source", help="EPUB or .txt")
    ap.add_argument("--chapters", help="1-based Chapter number or range, e.g. 3 or 2-5")
    ap.add_argument("--no-act", action="store_true", help="build: skip the IndexTTS-2 pass; already acted lines are still used")
    args = ap.parse_args()

    book_dir, book = load(args.source)
    if args.command == "list":
        for n, c in enumerate(book["chapters"]):
            print(f"{n + 1:3d}  {c['title']}  ({sum(len(p) for p in c['paragraphs'])} 字)")
        return
    if args.command == "status":
        status(book_dir, book)
        return
    ids = chapter_range(args.chapters, len(book["chapters"]))
    if args.command == "cast":
        cast = casting.run(book_dir, book, ids)
        said = casting.quotes_by_speaker(book_dir, book)
        for name, c in sorted(cast.items(), key=lambda kv: -len(said.get(kv[0], []))):
            print(f"{len(said.get(name, [])):5d}  {name}: {c['gender']} {c['age']} -> {c.get('voice') or c['type']}")
        return
    build(book_dir, book, ids, act=not args.no_act)


if __name__ == "__main__":
    main()
