"""Encodes Chapters as tagged .m4a files and joins them into one .m4b with chapter markers."""
import subprocess
import tempfile
from pathlib import Path

BITRATE = "64k"  # mono speech


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def chapter_file(wav, m4a, book, n, title):
    _ffmpeg("-i", str(wav), "-ac", "1", "-c:a", "aac", "-b:a", BITRATE,
            "-metadata", f"title={title}", "-metadata", f"album={book['title']}",
            "-metadata", f"artist={book['author']}", "-metadata", f"track={n + 1}", str(m4a))


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True)
    return float(out.stdout)


def m4b(chapters, out_path, book, cover=None):
    """chapters: [(m4a path, title)] in reading order."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "list.txt").write_text("".join(f"file '{p.resolve()}'\n" for p, _ in chapters), encoding="utf-8")
        meta = [";FFMETADATA1", f"title={book['title']}", f"artist={book['author']}", f"album={book['title']}",
                "genre=Audiobook"]
        start = 0.0
        for path, title in chapters:
            end = start + duration(path)
            meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(start * 1000)}", f"END={int(end * 1000)}",
                     f"title={title}"]
            start = end
        (tmp / "meta.txt").write_text("\n".join(meta) + "\n", encoding="utf-8")
        args = ["-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"), "-i", str(tmp / "meta.txt")]
        maps = ["-map", "0:a", "-map_metadata", "1", "-map_chapters", "1"]
        if cover:
            args += ["-i", str(cover)]
            maps += ["-map", "2:v", "-c:v", "copy", "-disposition:v", "attached_pic"]
        _ffmpeg(*args, *maps, "-c:a", "copy", "-f", "ipod", str(out_path))
