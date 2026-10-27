# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["mlx-audio==0.6.2", "numpy", "soundfile"]
# ///
"""Large Chinese TTS models through mlx-audio (Apple GPU).

Engines:
  qwen3      Qwen3-TTS 1.7B CustomVoice, a built-in preset speaker; --style adds a narrator
             instruction, --tags additionally gives confident dialogue its tagged emotion,
             --cast voices quoted speech by character (speakers come from --tags)
  audition   every voice in refs/voices.json reads a sample line
  voxcpm2    VoxCPM2 cloning from a designed Reference Clip (run `design` first)
  design     VoxCPM2 voice design: writes refs/<name>.wav + .txt from a text description,
             to be reused as the Reference Clip by voxcpm2 and CosyVoice3
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from mlx_audio.tts.utils import load_model  # noqa: E402

REFS = common.ROOT / "refs"
QWEN = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-bf16"
QWEN_BASE = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16"
VOXCPM2 = "mlx-community/VoxCPM2-bf16"

REF_TEXT = "那年冬天来得特别早，河面上结了一层薄冰。他背着旧帆布包，站在车站门口，看了很久很久。"
NARRATOR_STYLE = "用平稳自然的有声书旁白语气朗读，吐字清晰，语速适中，不拖音"
DIALOGUE_STYLE = "这是小说里人物说的话，用{emotion}的语气说，自然克制，不要夸张"
DEFAULT_DESIGN = "一位三十岁左右的女性有声书主播，普通话标准，音色温暖柔和，语速平稳，叙述自然有感情"


def _audio(results):
    rs = list(results)
    audio = np.concatenate([np.array(r.audio, dtype=np.float32).reshape(-1) for r in rs])
    return audio, rs[0].sample_rate


def qwen3(speaker, style=None, tags=None):
    """style: one instruction for every Segment. tags: emotion/tags_*.json from emotion/tag.py;
    only dialogue with a non-neutral emotion gets its own instruction, everything else keeps `style`."""
    model = load_model(QWEN)
    emotion = {}
    if tags:
        emotion = {t["text"]: t["emotion"] for t in json.loads(Path(tags).read_text(encoding="utf-8"))
                   if t["kind"] == "对白" and t["emotion"] != "平静" and t["confidence"] == "high"}

    def synth(text):
        instruct = DIALOGUE_STYLE.format(emotion=emotion[text]) if text in emotion else style
        return _audio(model.generate_custom_voice(text=text, speaker=speaker, language="Chinese", instruct=instruct))

    return synth


QUOTE_GAP_S = 0.12
LIBRARY = json.loads((REFS / "voices.json").read_text(encoding="utf-8"))


def resolve(voice):
    """A voice type from refs/voices.json (e.g. mid_f), a preset name, or ref:<name>."""
    return LIBRARY[voice]["voice"] if voice in LIBRARY else voice


def make_say():
    """say(text, voice, instruct): presets through CustomVoice; `ref:<name>` clones refs/<name>.wav
    through the Base model, which takes no instruction. Each model loads on first use."""
    models = {}

    def get(repo):
        if repo not in models:
            models[repo] = load_model(repo)
        return models[repo]

    def say(text, voice, instruct=None):
        voice = resolve(voice)
        if voice.startswith("ref:"):
            ref = voice[4:]
            return _audio(get(QWEN_BASE).generate(text=text, ref_audio=str(REFS / f"{ref}.wav"), lang_code="chinese",
                                                  ref_text=(REFS / f"{ref}.txt").read_text(encoding="utf-8").strip()))
        return _audio(get(QWEN).generate_custom_voice(text=text, speaker=voice, language="Chinese", instruct=instruct))

    return say


def qwen3_cast(narrator, style, tags, cast):
    """Narration in `narrator` with `style`; text inside “…” in the speaking character's voice.

    The speaker of each Segment comes from the tags; quotes can span Segments, so whether we are
    inside one carries over between calls.
    """
    say = make_say()
    speaker_of = {t["text"]: t["speaker"] for t in json.loads(Path(tags).read_text(encoding="utf-8"))}
    in_quote = False

    def synth(text):
        nonlocal in_quote
        parts, buf = [], ""
        for ch in text:
            if ch in "“”":
                if buf.strip():
                    parts.append((in_quote, buf))
                buf, in_quote = "", ch == "“"
            else:
                buf += ch
        if buf.strip():
            parts.append((in_quote, buf))

        voice = cast.get(speaker_of.get(text, ""), narrator)
        pieces, sr = [], None
        for quoted, part in parts:
            audio, sr = say(part, voice) if quoted else say(part, narrator, style)
            if pieces:
                pieces.append(np.zeros(int(QUOTE_GAP_S * sr), dtype=np.float32))
            pieces.append(audio)
        return np.concatenate(pieces), sr

    return synth


AUDITION_LINES = {
    "narrator": "那年冬天来得特别早。十一月刚过一半，河面上就结了一层薄冰。",
    "old_m": "孩子，路要一步一步走，急不得。当年我也是这么过来的。",
    "old_f": "天冷了，多穿件衣服，奶奶给你煮了一碗热汤。",
    "mid_m": "这件事我来处理，你们先回去，明天一早开会。",
    "mid_f": "你小时候天天来我这儿吃面，每次都要多加一个荷包蛋。",
    "young_m": "我在国外，接到电话的时候已经来不及了。",
    "young_f": "你别担心，我已经订好票了，周末就回来看你。",
    "teen_m": "老师，这道题我会做！让我上黑板试试吧。",
    "teen_f": "放学我们一起去书店吧，听说新到了好多漫画。",
    "child_m": "妈妈你看，我抓到一只蝴蝶！它的翅膀是蓝色的。",
    "child_f": "爸爸，我今天画了一只小兔子，送给你好不好？",
}


def audition():
    """Every library voice says a line that suits it, announced by the narrator:
    out/samples/voices/<type>.wav and one combined file."""
    say = make_say()
    narrator = LIBRARY["narrator"]
    style = NARRATOR_STYLE if narrator.get("style") else None
    out = common.OUT / "samples" / "voices"
    out.mkdir(parents=True, exist_ok=True)
    combined, sr = [], None
    for vid, v in LIBRARY.items():
        line, sr = say(AUDITION_LINES[vid], vid, style if vid == "narrator" else None)
        sf.write(out / f"{vid}.wav", line, sr)
        label, _ = say(f"{v['label']}。", "narrator", style)
        gap = np.zeros(int(0.4 * sr), dtype=np.float32)
        combined += [label, gap, line, gap, gap]
        print(f"{vid}: {len(line) / sr:.1f}s")
    sf.write(out / "all.wav", np.concatenate(combined), sr)


def voxcpm2(ref, quant):
    model = load_model(VOXCPM2.replace("-bf16", f"-{quant}"))
    wav = str(REFS / f"{ref}.wav")
    ref_text = (REFS / f"{ref}.txt").read_text(encoding="utf-8").strip()
    return lambda text: _audio(model.generate(text=text, ref_audio=wav, ref_text=ref_text))


def design(name, description, takes):
    """Writes several candidate takes; asr/pick_takes.py copies the chosen one to refs/<name>.wav."""
    REFS.mkdir(exist_ok=True)
    model = load_model(VOXCPM2)
    for i in range(takes):
        audio, sr = _audio(model.generate(text=REF_TEXT, instruct=description))
        path = REFS / f"{name}_take{i}.wav"
        sf.write(path, audio, sr)
        print(f"wrote {path} ({len(audio)/sr:.1f}s)")
    (REFS / f"{name}.txt").write_text(REF_TEXT, encoding="utf-8")


if __name__ == "__main__":
    ap = common.cli(__doc__)
    ap.add_argument("engine", choices=["qwen3", "voxcpm2", "design", "audition"])
    ap.add_argument("--speaker", default="Vivian", help="qwen3 preset speaker")
    ap.add_argument("--style", action="store_true", help="qwen3: steady audiobook-narrator instruction")
    ap.add_argument("--tags", help="qwen3: emotion tags from emotion/tag.py (implies --style)")
    ap.add_argument("--cast", help="qwen3: character voices, e.g. 林远=young_m,王阿姨=mid_f (needs --tags)")
    ap.add_argument("--ref", default="narrator_f", help="Reference Clip name under refs/")
    ap.add_argument("--describe", default=DEFAULT_DESIGN, help="design: voice description")
    ap.add_argument("--takes", type=int, default=3, help="design: number of candidate takes")
    ap.add_argument("--quant", default="bf16", choices=["bf16", "8bit", "4bit"], help="voxcpm2 weights")
    args = ap.parse_args()
    if args.engine == "design":
        design(args.ref, args.describe, args.takes)
    elif args.engine == "audition":
        audition()
    elif args.engine == "qwen3":
        style = NARRATOR_STYLE if args.style or args.tags else None
        if args.cast:
            cast = dict(kv.split("=") for kv in args.cast.split(","))
            name = f"qwen3_{args.speaker.lower()}_cast_" + "_".join(v.removeprefix("ref:") for v in cast.values())
            common.run(name, qwen3_cast(args.speaker, style, args.tags, cast), only=args.only)
            sys.exit()
        suffix = "_tagged" if args.tags else "_steady" if style else ""
        common.run(f"qwen3_{args.speaker.lower()}{suffix}", qwen3(args.speaker, style, args.tags), only=args.only)
    else:
        suffix = "" if args.quant == "bf16" else f"_{args.quant}"
        common.run(f"voxcpm2_{args.ref}{suffix}", voxcpm2(args.ref, args.quant), only=args.only)
