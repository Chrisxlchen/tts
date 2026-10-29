# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["mlx-lm>=0.28"]
# ///
"""Picks emotional dialogue from a built book for the emotion comparison.

Candidates are quoted lines of characters with their own voice that look charged (！？…, or an emotion cue
in the narration); a local LLM reads each with its context and names the emotion, a one-line delivery
direction and its confidence. Writes emotion/lines/lines.json with the confident, varied picks.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

from mlx_lm import generate, load

BOOK = Path(sys.argv[1])  # audiobook/work/<book>
LLM = "mlx-community/Qwen3-8B-4bit"
CUE = re.compile(r"怒|冷|笑|哭|颤|低声|咬牙|喊|吼|叫道|惊|恨|泣|哽|轻声|厉声|嘲|哼|急")
EMOTIONS = ["愤怒", "悲伤", "惊恐", "激动", "低声细语", "冷淡", "戏谑", "温柔", "平静"]
PROMPT = """你是有声书导演。下面是小说里的一段上下文，最后一段里引号中的台词由「{speaker}」说出。
请判断这句台词应该用什么情绪来演：
- emotion：从 {emotions} 中选一个
- direction：一句不超过 20 字的中文表演提示，比如“压着怒火，一字一顿”
- confidence：high / medium / low；只有上下文明确支持时才写 high

上下文：
{context}

台词：“{line}”

只输出 JSON：{{"emotion": "...", "direction": "...", "confidence": "..."}}"""

book = json.loads((BOOK / "book.json").read_text(encoding="utf-8"))
cast = json.loads((BOOK / "cast.json").read_text(encoding="utf-8"))
cands = []
for n, ch in enumerate(book["chapters"]):
    speakers = json.loads((BOOK / "speakers" / f"{n:03d}.json").read_text(encoding="utf-8"))
    paras = ch["paragraphs"]
    for i, who in speakers.items():
        i = int(i)
        if "voice" not in cast.get(who, {}):
            continue
        quotes = re.findall(r"“([^”]+)”", paras[i])
        if len(quotes) != 1 or not 6 <= len(quotes[0]) <= 45:
            continue
        narration = re.sub(r"“[^”]+”", "", paras[i])
        if re.search(r"[！？]|……", quotes[0]) or CUE.search(narration):
            cands.append({"chapter": n, "para": i, "speaker": who, "voice": cast[who]["voice"], "line": quotes[0],
                          "context": "\n".join(paras[max(0, i - 3):i + 1])})
print(f"{len(cands)} candidates", flush=True)
model, tok = load(LLM)
tagged = []
for c in cands[::max(1, len(cands) // 400)]:
    msg = PROMPT.format(speaker=c["speaker"], emotions="、".join(EMOTIONS), context=c["context"], line=c["line"])
    prompt = tok.apply_chat_template([{"role": "user", "content": msg}], add_generation_prompt=True,
                                     enable_thinking=False, tokenize=False)
    out = generate(model, tok, prompt=prompt, max_tokens=120)
    m = re.search(r"\{.*\}", out, re.S)
    try:
        tag = json.loads(m.group(0))
    except (AttributeError, json.JSONDecodeError):
        continue
    if tag.get("confidence") == "high" and tag.get("emotion") in EMOTIONS and tag["emotion"] != "平静":
        tagged.append(c | tag)
print(f"{len(tagged)} confident", flush=True)
# 14 lines: at most 2 per emotion and 3 per character, spread over the volume
picks, per_emo, per_who = [], Counter(), Counter()
for c in tagged:
    if per_emo[c["emotion"]] < 2 and per_who[c["speaker"]] < 3:
        picks.append(c); per_emo[c["emotion"]] += 1; per_who[c["speaker"]] += 1
    if len(picks) == 14:
        break
out = Path(__file__).parent / "lines" / "lines.json"
out.write_text(json.dumps(picks, ensure_ascii=False, indent=1), encoding="utf-8")
for p in picks:
    print(p["emotion"], p["speaker"], p["line"], "|", p["direction"])
