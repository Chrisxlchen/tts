"""Acted Lines: dialogue the author marks with an emotion, voiced by IndexTTS-2; the rest stays Qwen3 cloning.

The emotion blind tests (../bakeoff/emotion/RESULTS.md) found IndexTTS-2 better on fear, anger and excitement,
and no better on quieter emotions. Acting every line an LLM read as charged made the dialogue overwrought, so only
a quote whose own paragraph names one of those emotions in the narration (怒道, 厉声, 颤声, 害怕道, 激动……) is
acted, and the performance cue is the author's clause itself; nothing is guessed. Every other line is spoken plainly.

  moods() {paragraph: (emotion, the author's clause)} for a Chapter's Acted Lines
  jobs()  acted/jobs.json: every quoted part to act, keyed like synth.act_key()
  act()   runs act_index.py in IndexTTS-2's own venv, writing acted/<key>.wav

IndexTTS-2 cannot share memory with the TTS build, so this runs as its own pass before the build.
"""
import json
import re
import subprocess
import time
from pathlib import Path

CUES = {  # words that state the emotion outright; 怒 alone would also catch 怒涛, 惊 alone mere surprise
    "愤怒": r"怒道|怒吼|怒喝|怒斥|怒声|怒视|怒骂|大怒|愤怒|恼怒|发怒|怒气|怒极|怒不可遏|厉声|喝道|吼道|咆哮|咬牙切齿|呵斥|斥道|骂道",
    "惊恐": r"惊恐|惊叫|惊呼|颤声|颤抖|恐惧|害怕|尖叫|失声|惶恐|惊慌|骇然|战栗",
    "激动": r"激动|兴奋|狂喜|欢呼|大喜|喜道|欣喜若狂|振奋|雀跃|兴高采烈",
}
# a cue followed by 的 describes something else (学生们惊恐的脸), not how the line is said
CUE = re.compile("|".join(f"(?P<{['anger', 'fear', 'joy'][i]}>(?:{c})(?!的))" for i, c in enumerate(CUES.values())))
INDEX_TTS = Path(__file__).resolve().parents[1] / "bakeoff" / "vendor" / "index-tts"


def cue(paragraph):
    """(emotion, the author's clause naming it) from the narration around a quote, or None."""
    if "“" not in paragraph:
        return None
    for piece in re.split(r"“[^”]*”", paragraph):
        if m := CUE.search(piece):
            emotion = list(CUES)[["anger", "fear", "joy"].index(m.lastgroup)]
            clause = re.split(r"[，。！？；：]", piece[m.start():])[0]
            head = re.split(r"[，。！？；：]", piece[:m.start()])[-1]
            return emotion, (head + clause)[-20:]
    return None


def moods(book_dir, book, n):
    """{paragraph: (emotion, direction)} for a Chapter's Acted Lines: attributed quotes the author marks."""
    speakers = json.loads((book_dir / "speakers" / f"{n:03d}.json").read_text(encoding="utf-8"))
    paras = book["chapters"][n]["paragraphs"]
    return {p: m for p in speakers if (m := cue(paras[int(p)]))}


def act_ref(voice):
    """The clip IndexTTS-2 clones for a voice: its reference clip, or for a preset voice (which has none)
    refs/preset_<name>.wav, a padded neutral sample of that preset. None when neither exists."""
    import synth

    if wav := synth.ref_wav(voice):
        return wav
    preset = synth.mlx_tts.REFS / f"preset_{synth.mlx_tts.resolve(voice)}.wav"
    return str(preset) if preset.exists() else None


def jobs(book_dir, book, cast, ids):
    import synth

    out = []
    for n in ids:
        mood = moods(book_dir, book, n)
        speakers = json.loads((book_dir / "speakers" / f"{n:03d}.json").read_text(encoding="utf-8"))
        for p, m in mood.items():
            c = cast.get(speakers.get(p))
            if not c:
                continue
            voice = c.get("voice") or c["type"]
            if not act_ref(voice):
                continue
            for _, parts in synth.voice_parts(book["chapters"][n]["paragraphs"][int(p)]):
                for quoted, text in parts:
                    if quoted and synth.SPEAKABLE.search(text):
                        line = synth.speakable(text)
                        out.append({"chapter": n, "key": synth.act_key(line, voice, m), "text": line, "ref": act_ref(voice),
                                    "emotion": m[0], "direction": m[1]})
    acted = book_dir / "acted"
    acted.mkdir(exist_ok=True)
    (acted / "jobs.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def act(book_dir, book, cast, ids):
    todo = [j for j in jobs(book_dir, book, cast, ids) if not (book_dir / "acted" / f"{j['key']}.wav").exists()]
    print(f"[act] {len(todo)} lines to act with IndexTTS-2", flush=True)
    if not todo:
        return
    # IndexTTS-2 peaks at about half of a 36 GB Mac, and macOS sometimes kills it; finished lines are kept,
    # so another run picks up where it stopped. It is mostly killed while loading, so give up only after
    # six runs in a row that act nothing.
    left = lambda: sum(1 for j in todo if not (book_dir / "acted" / f"{j['key']}.wav").exists())
    idle = 0
    while idle < 6:
        before = left()
        run = subprocess.run(["uv", "run", "python", str(Path(__file__).resolve().parent / "act_index.py"),
                              str(book_dir / "acted")], cwd=INDEX_TTS)
        if run.returncode == 0:
            return
        idle = idle + 1 if left() == before else 0
        print(f"[act] IndexTTS-2 exited with {run.returncode}, {left()} lines left, retrying", flush=True)
        time.sleep(30)
    raise subprocess.CalledProcessError(run.returncode, run.args)
