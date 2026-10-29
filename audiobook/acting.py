"""Acted Lines: charged dialogue voiced by IndexTTS-2 with the director's emotion, the rest stays Qwen3 cloning.

The emotion blind tests (../bakeoff/emotion/RESULTS.md) found IndexTTS-2 better on fear, anger and excitement
in both rounds, a tie on mockery, and no better or worse on cold, quiet-sad or gentle lines. So only quoted speech
that a local LLM tags with one of ACTED at high confidence is acted; everything else keeps the steady voice.

  tag()   emotions/NNN.json: {paragraph: {emotion, direction, confidence}} for charged dialogue
  jobs()  acted/jobs.json: every quoted part to act, keyed like synth.act_key()
  act()   runs act_index.py in IndexTTS-2's own venv, writing acted/<key>.wav

IndexTTS-2 cannot share memory with the TTS build, so this runs as its own pass before the build.
"""
import json
import re
import subprocess
from pathlib import Path

LLM = "mlx-community/Qwen3-8B-4bit"  # what the blind test's tags came from
ACTED = ("惊恐", "愤怒", "激动")
EMOTIONS = ["愤怒", "悲伤", "惊恐", "激动", "低声细语", "冷淡", "戏谑", "温柔", "平静"]
CUE = re.compile(r"怒|冷|笑|哭|颤|低声|咬牙|喊|吼|叫道|惊|恨|泣|哽|轻声|厉声|嘲|哼|急")
INDEX_TTS = Path(__file__).resolve().parents[1] / "bakeoff" / "vendor" / "index-tts"
PROMPT = """你是有声书导演。下面是小说里的一段上下文，最后一段里引号中的台词由「{speaker}」说出。
请判断这句台词应该用什么情绪来演：
- emotion：从 {emotions} 中选一个
- direction：一句不超过 20 字的中文表演提示，比如“压着怒火，一字一顿”
- confidence：high / medium / low；只有上下文明确支持时才写 high

上下文：
{context}

台词：{line}

只输出 JSON：{{"emotion": "...", "direction": "...", "confidence": "..."}}"""


def charged(paragraph):
    """Dialogue worth asking the director about: an exclamation, question or trailing off in the quote,
    or an emotion cue in the narration around it."""
    quotes = "".join(re.findall(r"“([^”]+)”", paragraph))
    return bool(quotes) and bool(re.search(r"[！？]|……", quotes) or CUE.search(re.sub(r"“[^”]+”", "", paragraph)))


def tag(book_dir, book, ids):
    out_dir = book_dir / "emotions"
    out_dir.mkdir(exist_ok=True)
    todo = [n for n in ids if not (out_dir / f"{n:03d}.json").exists()]
    if not todo:
        return
    from mlx_lm import generate, load

    model, tok = load(LLM)
    for n in todo:
        paras = book["chapters"][n]["paragraphs"]
        speakers = json.loads((book_dir / "speakers" / f"{n:03d}.json").read_text(encoding="utf-8"))
        tags = {}
        for p, who in speakers.items():
            if not charged(paras[int(p)]):
                continue
            i = int(p)
            msg = PROMPT.format(speaker=who, emotions="、".join(EMOTIONS), context="\n".join(paras[max(0, i - 3):i + 1]),
                                line="“" + "”“".join(re.findall(r"“([^”]+)”", paras[i])) + "”")
            prompt = tok.apply_chat_template([{"role": "user", "content": msg}], add_generation_prompt=True,
                                             enable_thinking=False, tokenize=False)
            m = re.search(r"\{.*\}", generate(model, tok, prompt=prompt, max_tokens=120), re.S)
            try:
                tags[p] = json.loads(m.group(0))
            except (AttributeError, json.JSONDecodeError):
                continue
        (out_dir / f"{n:03d}.json").write_text(json.dumps(tags, ensure_ascii=False, indent=1), encoding="utf-8")
        acted = sum(1 for t in tags.values() if is_acted(t))
        print(f"[emotion] {n + 1:03d} {book['chapters'][n]['title']}: {len(tags)} charged, {acted} acted", flush=True)


def is_acted(t):
    return t.get("confidence") == "high" and t.get("emotion") in ACTED and bool(t.get("direction"))


def moods(book_dir, n):
    """{paragraph: (emotion, direction)} for a Chapter's Acted Lines; empty before tag() ran."""
    path = book_dir / "emotions" / f"{n:03d}.json"
    if not path.exists():
        return {}
    tags = json.loads(path.read_text(encoding="utf-8"))
    return {p: (t["emotion"], t["direction"]) for p, t in tags.items() if is_acted(t)}


def jobs(book_dir, book, cast, ids):
    import synth

    out = []
    for n in ids:
        mood = moods(book_dir, n)
        speakers = json.loads((book_dir / "speakers" / f"{n:03d}.json").read_text(encoding="utf-8"))
        for p, m in mood.items():
            c = cast.get(speakers.get(p))
            if not c:
                continue
            voice = c.get("voice") or c["type"]
            for _, parts in synth.voice_parts(book["chapters"][n]["paragraphs"][int(p)]):
                for quoted, text in parts:
                    if quoted and synth.SPEAKABLE.search(text):
                        line = synth.speakable(text)
                        out.append({"chapter": n, "key": synth.act_key(line, voice, m), "text": line, "ref": synth.ref_wav(voice),
                                    "emotion": m[0], "direction": m[1]})
    acted = book_dir / "acted"
    acted.mkdir(exist_ok=True)
    (acted / "jobs.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def stale(book_dir, n, m4a):
    """A rendered Chapter is stale when one of its Acted Lines was acted after it was exported."""
    path = book_dir / "acted" / "jobs.json"
    if not path.exists():
        return False
    done = m4a.stat().st_mtime
    for j in json.loads(path.read_text(encoding="utf-8")):
        wav = book_dir / "acted" / f"{j['key']}.wav"
        if j.get("chapter") == n and wav.exists() and wav.stat().st_mtime > done:
            return True
    return False


def act(book_dir, book, cast, ids):
    todo = [j for j in jobs(book_dir, book, cast, ids) if not (book_dir / "acted" / f"{j['key']}.wav").exists()]
    print(f"[act] {len(todo)} lines to act with IndexTTS-2", flush=True)
    # IndexTTS-2 peaks at about half of a 36 GB Mac, and macOS sometimes kills it while loading; finished
    # lines are kept, so another run picks up where it stopped.
    for attempt in range(3):
        run = subprocess.run(["uv", "run", "python", str(Path(__file__).resolve().parent / "act_index.py"),
                              str(book_dir / "acted")], cwd=INDEX_TTS)
        if run.returncode == 0:
            return
        print(f"[act] IndexTTS-2 exited with {run.returncode}, retrying", flush=True)
    raise subprocess.CalledProcessError(run.returncode, run.args)
