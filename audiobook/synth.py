"""Renders Chapters to audio: narration in the Narrator Voice, quoted speech in Character Voices.

Every Segment is ASR-checked and re-generated (up to MAX_TRIES, keeping the best take) when its
syllable error rate is above BAD_RATE. Syllables are compared as toneless pinyin, so the
recogniser writing a homophone (她/他, 师父/师傅, 嫁嫁/佳佳) is not counted as a misreading. Takes are cached under seg/ by content, so an interrupted run resumes
where it stopped and re-running after a cast.json edit only redoes the affected Segments.
"""
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr
from pypinyin import lazy_pinyin

BAKEOFF = Path(__file__).resolve().parents[1] / "bakeoff"
sys.path[:0] = [str(BAKEOFF), str(BAKEOFF / "engines"), str(BAKEOFF / "asr")]
import common  # noqa: E402
import mlx_tts  # noqa: E402
import score  # noqa: E402

MAX_TRIES = 3
BAD_RATE = 0.10
QUOTE_GAP_S = mlx_tts.QUOTE_GAP_S
TARGET_DBFS = -20.0  # every voice is levelled to this, so dialogue does not jump in loudness against narration
CACHE_VERSION = 2  # bump when rendering changes, so cached takes are redone


def level(audio):
    """Scales speech to TARGET_DBFS, measured over the louder (voiced) frames only."""
    frames = audio[: len(audio) // 480 * 480].reshape(-1, 480)
    if not len(frames):
        return audio
    rms = np.sqrt((frames ** 2).mean(axis=1))
    voiced = rms[rms > rms.max() * 0.1]
    gain = 10 ** (TARGET_DBFS / 20) / max(float(np.sqrt((voiced ** 2).mean())), 1e-6)
    gain = min(gain, 0.98 / max(float(np.abs(audio).max()), 1e-6))  # never clip
    return (audio * gain).astype(np.float32)
OPEN, CLOSE = "“「", "”」"
SPEAKABLE = re.compile(r"[0-9A-Za-z㐀-鿿]")
ELLIPSIS = re.compile(r"(?:…|\.{2,}|。{2,}|·{2,})+")
BEAT_S = 0.5  # a part with nothing to read ("……", “……”) is a silent beat, not a TTS call
SCENE_BREAK_S = 1.5  # a separator line such as "-----"


def speakable(text):
    """The text as the TTS should read it. An ellipsis makes the model fill the gap with noise,
    so one inside a sentence becomes a comma pause and a trailing one a full stop."""
    if not ELLIPSIS.search(text):
        return text
    text = ELLIPSIS.sub("，", text).strip()
    text = re.sub(r"，+(?=[，。！？；：、—])", "", text)  # "……？" keeps only the question mark
    text = re.sub(r"^[，。！？；：、\s]+", "", text)
    return re.sub(r"，+$", "。", text)


def syllables(text):
    return lazy_pinyin(score.normalize(text))


def error_rate(ref, hyp):
    """Edit distance between the toneless pinyin of `ref` and `hyp`, per reference syllable."""
    ref, hyp = syllables(ref), syllables(hyp)
    if not ref:
        return 0.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)


MAX_S_PER_SYLLABLE = 0.6  # about twice normal pace: the model babbled or repeated itself, which ASR can miss


def too_slow(ref, audio, sr):
    n = len(syllables(ref))
    return n >= 4 and len(audio) / sr / n > MAX_S_PER_SYLLABLE


FILLER = re.compile(r"^[，。\s]*[啊嗯呃哦]")


def stray_start(ref, hyp):
    """A cloned voice sometimes opens with a syllable carried over from its reference clip."""
    return bool(FILLER.match(hyp)) and not FILLER.match(re.sub(r"^[“「]", "", ref))


def voice_parts(paragraph):
    """Splits a paragraph into its Segments, each a list of (quoted, text) parts."""
    in_quote = False
    out = []
    for segment in common.split_paragraph(paragraph):
        parts, buf = [], ""
        for ch in segment:
            if ch in OPEN or ch in CLOSE:
                if buf.strip():
                    parts.append((in_quote, buf))
                buf, in_quote = "", ch in OPEN
            else:
                buf += ch
        if buf.strip():
            parts.append((in_quote, buf))
        out.append((segment, parts))
    return out


CLIPS = {}


def ref_wav(voice):
    """The reference clip a cloned voice reads from, or None for a preset."""
    ref = mlx_tts.resolve(voice)
    return str(mlx_tts.REFS / f"{ref[4:]}.wav") if ref.startswith("ref:") else None


def clip_id(voice):
    """A fingerprint of the reference clip a cloned voice uses, so replacing the clip redoes its Segments."""
    wav = ref_wav(voice)
    if not wav:
        return mlx_tts.resolve(voice)
    if wav not in CLIPS:
        CLIPS[wav] = hashlib.sha1(Path(wav).read_bytes()).hexdigest()[:8]
    return CLIPS[wav]


def act_key(line, voice, mood):
    """Names an Acted Line's take in acted/: its text, the character's clip and the (emotion, direction)."""
    return hashlib.sha1(json.dumps([line, voice, clip_id(voice), list(mood)], ensure_ascii=False).encode()).hexdigest()[:16]


class Renderer:
    def __init__(self, book_dir, cast):
        self.seg_dir = book_dir / "seg"
        self.seg_dir.mkdir(exist_ok=True)
        self.acted_dir = book_dir / "acted"
        self.cast = cast
        self.say = mlx_tts.make_say()
        narrator = mlx_tts.LIBRARY["narrator"]
        self.narrator = ("narrator", mlx_tts.NARRATOR_STYLE if narrator.get("style") else None)
        self.rec = score.recognizer()

    def voice_of(self, name):
        c = self.cast.get(name)
        return (c.get("voice") or c["type"], None) if c else self.narrator

    def quote_voice(self, text, speaker, mood):
        """A character's voice for a quoted part: `acted:<key>|<voice>` when IndexTTS-2 has acted the line."""
        voice, instruct = self.voice_of(speaker)
        if mood and speaker in self.cast:
            key = act_key(speakable(text), voice, mood)
            if (self.acted_dir / f"{key}.wav").exists():
                return f"acted:{key}|{voice}", instruct
        return voice, instruct

    @staticmethod
    def clip_id(voice):
        return voice.partition("|")[0] if voice.startswith("acted:") else clip_id(voice)

    def speak(self, text, voice, instruct, attempt):
        """The acted take on the first attempt; if the ASR check sends the Segment back, the steady voice."""
        if voice.startswith("acted:"):
            key, _, fallback = voice[6:].partition("|")
            if attempt == 1:
                audio, sr = sf.read(self.acted_dir / f"{key}.wav", dtype="float32")
                return soxr.resample(audio, sr, 24000), 24000
            voice = fallback
        return self.say(text, voice, instruct)

    def transcribe(self, audio, sr):
        s = self.rec.create_stream()
        s.accept_waveform(16000, soxr.resample(audio, sr, 16000))
        self.rec.decode_stream(s)
        return s.result.text

    def segment(self, parts, speaker, mood=None):
        """[(quoted, text)] -> (audio, sr, info); cached by text and voices. `mood` (emotion, direction) marks
        the paragraph's quoted speech as an Acted Line."""
        plan = [(speakable(text), *(self.quote_voice(text, speaker, mood) if quoted else self.narrator))
                for quoted, text in parts if SPEAKABLE.search(text)]
        if not plan:
            sr = 24000
            raw = "".join(text for _, text in parts)
            pause = SCENE_BREAK_S if re.search(r"[-—*=~]{3,}", raw) else BEAT_S
            return np.zeros(int(pause * sr), dtype=np.float32), sr, {"err": 0.0, "tries": 0, "gen_s": 0.0,
                                                                     "cached": True, "asr": ""}
        clips = sorted({self.clip_id(voice) for _, voice, _ in plan})
        key = hashlib.sha1(json.dumps([CACHE_VERSION, plan, clips], ensure_ascii=False).encode()).hexdigest()[:16]
        wav, meta = self.seg_dir / f"{key}.wav", self.seg_dir / f"{key}.json"
        if wav.exists() and meta.exists():
            audio, sr = sf.read(wav, dtype="float32")
            return audio, sr, json.loads(meta.read_text(encoding="utf-8")) | {"cached": True}

        ref = "".join(text for text, _, _ in plan)
        best, t0 = None, time.perf_counter()
        for attempt in range(1, MAX_TRIES + 1):
            pieces, sr = [], None
            for text, voice, instruct in plan:
                audio, sr = self.speak(text, voice, instruct, attempt)
                if pieces:
                    pieces.append(np.zeros(int(QUOTE_GAP_S * sr), dtype=np.float32))
                pieces.append(level(np.asarray(audio, dtype=np.float32).reshape(-1)))
            audio = np.concatenate(pieces)
            hyp = self.transcribe(audio, sr)
            err = error_rate(ref, hyp) + (0.5 if too_slow(ref, audio, sr) or stray_start(ref, hyp) else 0.0)
            if best is None or err < best[2]:
                best = (audio, sr, err, hyp, attempt)
            if err <= BAD_RATE:
                break
        audio, sr, err, hyp, attempt = best
        info = {"plan": plan, "err": err, "asr": hyp, "tries": attempt, "gen_s": time.perf_counter() - t0}
        sf.write(wav, audio, sr)
        meta.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        return audio, sr, info

    def chapter(self, chapter, speakers, moods=None):
        """Returns (audio, sr, report). The narrator reads the chapter title first. `moods`: acting.moods()."""
        moods = moods or {}
        pieces, segments, sr = [], [], None
        title_audio, sr, _ = self.segment([(False, chapter["title"] + "。")], None)
        pieces.append(title_audio)
        for p, paragraph in enumerate(chapter["paragraphs"]):
            for s, (text, parts) in enumerate(voice_parts(paragraph)):
                audio, sr, info = self.segment(parts, speakers.get(str(p)), moods.get(str(p)))
                gap = common.SENTENCE_GAP_S if s else common.PARAGRAPH_GAP_S
                pieces += [np.zeros(int(gap * sr), dtype=np.float32), audio]
                segments.append({"p": p, "text": text, "audio_s": len(audio) / sr,
                                 **{k: info.get(k) for k in ("err", "asr", "tries", "gen_s", "cached")}})
        audio = np.concatenate(pieces)
        fresh = [s for s in segments if not s["cached"]]
        report = {
            "title": chapter["title"], "audio_s": len(audio) / sr,
            "gen_s": sum(s["gen_s"] for s in fresh),
            "still_bad": [s for s in segments if s["err"] > BAD_RATE],
            "retried": sum(1 for s in segments if s["tries"] > 1),
            "segments": segments,
        }
        return audio, sr, report
