# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["mlx-lm>=0.28", "numpy", "soundfile"]
# ///
"""Has a local LLM read the whole passage and tag every Segment's speaker and emotion.

Writes emotion/tags_<item>.json: [{"n", "text", "kind", "speaker", "emotion", "confidence"}].
The TTS engine turns only confident dialogue tags into emotion instructions (see mlx_tts.py).
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import common  # noqa: E402

from mlx_lm import generate, load  # noqa: E402

LLM = "mlx-community/Qwen3-8B-4bit"

PROMPT = """你是有声书导演。下面是一章小说，已经切成编号的朗读片段。请通读全文、理解剧情后，为每个片段标注：
- kind：旁白 / 对白 / 混合（片段里既有叙述又有引号里的台词）
- speaker：台词是谁说的；纯旁白写"旁白"
- emotion：朗读这段时应有的情绪，用一个简短的中文词，比如 平静、惊喜、感慨、悲伤、激动、温和、犹豫。没有明显情绪就写"平静"
- confidence：你对 emotion 判断的把握，high / medium / low。只有上下文明确支持时才写 high

全文：
{chapter}

片段：
{segments}

只输出一个 JSON 数组，每个元素形如 {{"n": 0, "kind": "旁白", "speaker": "旁白", "emotion": "平静", "confidence": "high"}}，按编号顺序覆盖所有片段，不要输出其他内容。"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--item", default="passage")
    args = ap.parse_args()

    paragraphs = dict(common.load_items())[args.item]
    segments = [s for p in paragraphs for s in common.split_paragraph(p)]
    prompt = PROMPT.format(chapter="\n".join(paragraphs),
                           segments="\n".join(f"[{i}] {s}" for i, s in enumerate(segments)))

    model, tokenizer = load(LLM)
    chat = tokenizer.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True,
                                         enable_thinking=False, tokenize=False)
    reply = generate(model, tokenizer, prompt=chat, max_tokens=4096, verbose=False)
    tags = json.loads(re.search(r"\[.*\]", reply, re.S).group(0))
    by_n = {t["n"]: t for t in tags}
    missing = [i for i in range(len(segments)) if i not in by_n]
    if missing:
        raise SystemExit(f"LLM skipped segments {missing}:\n{reply}")

    out = [{"n": i, "text": s, **{k: by_n[i][k] for k in ("kind", "speaker", "emotion", "confidence")}}
           for i, s in enumerate(segments)]
    path = Path(__file__).parent / f"tags_{args.item}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for t in out:
        print(f"[{t['n']:02d}] {t['kind']}/{t['speaker']}/{t['emotion']}/{t['confidence']}  {t['text'][:30]}")


if __name__ == "__main__":
    main()
