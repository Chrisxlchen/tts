"""Has a local LLM attribute quoted speech to characters and give each character a Voice Type.

Per book this keeps cast.json: {name: {"gender", "age", "type", "voice"?}}. A character's type is
fixed the first time they appear, and existing entries are never rewritten, so editing cast.json
by hand (changing "type", or adding "voice": "ref:<name>" / a preset) sticks across reruns.
Per Chapter it writes speakers/<n>.json: {paragraph index: character name}.
"""
import json
import re
from pathlib import Path

LLM = "mlx-community/Qwen3-30B-A3B-4bit"  # MoE: 30B quality at ~3B speed
WINDOW_CHARS = 6000  # chapter text per LLM call; longer chapters are read in windows
THINK_BUDGET = 3000  # reasoning tokens before the model is made to answer; reasoning markedly helps accuracy
ANSWER_TOKENS = 2500
FORCE_ANSWER = "\n\n时间有限，我现在根据已有的分析直接给出答案。\n</think>\n\n"
QUOTE = re.compile(r"[“「]")
NOT_A_NAME = ("未知", "旁白", "不明", "无")  # the LLM sometimes lists these as characters; their lines stay with the narrator

SPEECH_VERB = "说|问|道|喊|叫|答|嚷|嘀咕|开口"
OUTSIDE_QUOTES = re.compile(r"[“「][^”」]*[”」]?")

TYPES = {("男", "老年"): "old_m", ("女", "老年"): "old_f", ("男", "中年"): "mid_m", ("女", "中年"): "mid_f",
         ("男", "青年"): "young_m", ("女", "青年"): "young_f", ("男", "少年"): "teen_m", ("女", "少年"): "teen_f",
         ("男", "儿童"): "child_m", ("女", "儿童"): "child_f"}

DESCRIBE = """下面是一段小说。请判断这些说话的角色的性别（男/女）和年龄段（老年/中年/青年/少年/儿童）：{names}

{text}

只输出 JSON 数组，不要输出其他内容：[{{"name": "角色名", "gender": "男", "age": "青年"}}, ...]"""

PROMPT = """你是有声书导演，要给小说里的台词分配配音演员。下面是一章小说的一部分，每段前有编号。

前文已出现的角色（如果台词出自他们，沿用这里的名字；同一人的别名、称呼也归到这个名字）：
{known}

请完成两件事：
1. 对每个含有引号台词的段落（编号：{quoted}），判断引号里的话是谁说的。要根据本部分的情节逐段推断：说话人常常是本部分才出场的新角色，不要因为某个已知角色在场就把台词归给他。无法确定时写"未知"。
2. 列出所有说过话、但不在已知列表里的角色，给出性别（男/女）和年龄段（老年/中年/青年/少年/儿童）。如果后文给出了名字就用名字，否则用描述性称呼（例如"小女孩"、"司机"）。第 1 步里用到的每个新名字都必须出现在这里。

正文：
{text}

只输出一个 JSON 对象，不要输出其他内容：
{{"speakers": {{"段落编号": "角色名", ...}}, "new_characters": [{{"name": "角色名", "gender": "男", "age": "青年"}}, ...]}}"""


def explicit_speaker(paragraph, names):
    """The one known character the narration names right before a speech verb ("林远说"), if any."""
    narration = OUTSIDE_QUOTES.sub("|", paragraph)
    hits = {n for n in names if re.search(rf"{re.escape(n)}[^|。！？]{{0,6}}?(?:{SPEECH_VERB})", narration)}
    return hits.pop() if len(hits) == 1 else None


def _windows(paragraphs):
    window, size = [], 0
    for i, p in enumerate(paragraphs):
        if window and size + len(p) > WINDOW_CHARS:
            yield window
            window, size = [], 0
        window.append(i)
        size += len(p)
    if window:
        yield window


class Caster:
    def __init__(self):
        from mlx_lm import load

        self.model, self.tokenizer = load(LLM)

    def _generate(self, prompt, max_tokens):
        from mlx_lm import generate

        return generate(self.model, self.tokenizer, prompt=prompt, max_tokens=max_tokens, verbose=False)

    def ask(self, prompt, think=True):
        """Reasons for at most THINK_BUDGET tokens, then answers; returns the parsed JSON."""
        chat = self.tokenizer.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True,
                                                  enable_thinking=think, tokenize=False)
        reply = self._generate(chat, THINK_BUDGET if think else ANSWER_TOKENS)
        if think and "</think>" not in reply:
            reply += FORCE_ANSWER
            reply += self._generate(chat + reply, ANSWER_TOKENS)
        answer = reply.split("</think>")[-1]
        match = re.search(r"[\[{].*[\]}]", answer, re.S)
        if not match:
            raise ValueError(f"no JSON in LLM answer: {answer[-300:]!r}")
        return json.loads(match.group(0))

    def describe(self, names, text, cast):
        """Asks gender and age for speakers the main pass named but did not describe."""
        try:
            for c in self.ask(DESCRIBE.format(names="、".join(names), text=text), think=False):
                self._add(cast, c)
        except (ValueError, json.JSONDecodeError):
            pass

    @staticmethod
    def _add(cast, c):
        name, gender, age = c.get("name"), c.get("gender"), c.get("age")
        if name and name not in cast and name not in NOT_A_NAME and (gender, age) in TYPES:
            cast[name] = {"gender": gender, "age": age, "type": TYPES[(gender, age)]}

    def cast_chapter(self, paragraphs, cast):
        """Returns {paragraph index: name} and adds newly met characters to `cast` in place."""
        speakers = {}
        for window in _windows(paragraphs):
            quoted = [i for i in window if QUOTE.search(paragraphs[i])]
            if not quoted:
                continue
            known = "\n".join(f"- {n}（{c['gender']}，{c['age']}）" for n, c in cast.items()) or "（暂无）"
            text = "\n".join(f"[{i}] {paragraphs[i]}" for i in window)
            prompt = PROMPT.format(known=known, quoted="、".join(map(str, quoted)), text=text)
            try:
                reply = self.ask(prompt)
            except (ValueError, json.JSONDecodeError):
                reply = self.ask(prompt, think=False)
            for c in reply.get("new_characters", []):
                self._add(cast, c)
            unknown = {n for n in reply.get("speakers", {}).values() if n not in cast and n not in NOT_A_NAME}
            if unknown:
                self.describe(sorted(unknown), text, cast)
            for i, name in reply.get("speakers", {}).items():
                if str(i).isdigit() and int(i) in quoted and name in cast:
                    speakers[int(i)] = name
            for i in quoted:  # an explicit "林远说" beats the LLM's reading
                named = explicit_speaker(paragraphs[i], cast)
                if named:
                    speakers[i] = named
        return speakers


def run(book_dir, book, chapter_ids):
    """Casts every requested Chapter that has no speakers file yet."""
    cast_path = book_dir / "cast.json"
    cast = json.loads(cast_path.read_text(encoding="utf-8")) if cast_path.exists() else {}
    (book_dir / "speakers").mkdir(exist_ok=True)
    todo = [n for n in chapter_ids if not (book_dir / "speakers" / f"{n:03d}.json").exists()]
    whole_book = len(list((book_dir / "speakers").glob("*.json"))) + len(todo) == len(book["chapters"])
    assigned = book_dir / "voices.assigned"  # delete it to re-run the main-character assignment
    if not todo and (not whole_book or assigned.exists()):
        return cast
    caster = Caster()
    for n in todo:
        chapter = book["chapters"][n]
        speakers = caster.cast_chapter(chapter["paragraphs"], cast)
        (book_dir / "speakers" / f"{n:03d}.json").write_text(json.dumps(speakers, ensure_ascii=False, indent=1),
                                                             encoding="utf-8")
        cast_path.write_text(json.dumps(cast, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[cast] {chapter['title']}: {len(speakers)} quoted paragraphs, {len(cast)} characters so far",
              flush=True)
    # Main characters can only be told apart once the whole book is cast.
    if whole_book:
        if assign_voices(book_dir, book, cast, caster):
            cast_path.write_text(json.dumps(cast, ensure_ascii=False, indent=1), encoding="utf-8")
        assigned.touch()
    return cast


VOICES = Path(__file__).resolve().parents[1] / "bakeoff" / "refs" / "voices.json"
MIN_LINES = 5  # characters with fewer quoted paragraphs than this are minor and keep the type's base voice

MATCH = """你是有声书导演。下面几位角色属于同一种音色类型，每人要分配一个不同的音色。根据他们的台词判断性格，为每人挑一个最合适的音色，每个音色只能用一次。

可选音色：
{voices}

角色和部分台词：
{characters}

只输出 JSON 对象，不要输出其他内容：{{"角色名": "音色编号", ...}}"""


def quotes_by_speaker(book_dir, book):
    """{name: [quoted text, ...]} over every cast Chapter."""
    out = {}
    for path in sorted((book_dir / "speakers").glob("*.json")):
        paragraphs = book["chapters"][int(path.stem)]["paragraphs"]
        for i, name in json.loads(path.read_text(encoding="utf-8")).items():
            said = re.findall(r"[“「]([^”」]+)", paragraphs[int(i)])
            out.setdefault(name, []).extend(said)
    return out


def assign_voices(book_dir, book, cast, caster=None):
    """Gives the main characters of each Voice Type that has variants a variant of their own.

    Only characters without a "voice" are touched, so hand edits in cast.json stick.
    Returns True if cast changed.
    """
    library = json.loads(VOICES.read_text(encoding="utf-8"))
    said = quotes_by_speaker(book_dir, book)
    changed = False
    for base in sorted({v["variant_of"] for v in library.values() if "variant_of" in v}):
        taken = {c.get("voice") for c in cast.values()}
        free = [k for k, v in library.items() if v.get("variant_of") == base and k not in taken]
        ranked = sorted((n for n, c in cast.items() if c["type"] == base and not c.get("voice")
                         and len(said.get(n, [])) >= MIN_LINES), key=lambda n: -len(said[n]))
        main = ranked[:len(free)]
        if not main:
            continue
        pairing = {}
        if caster and len(main) > 1:
            try:
                reply = caster.ask(MATCH.format(
                    voices="\n".join(f"- {k}：{library[k]['label']}" for k in free),
                    characters="\n".join(f"- {n}：" + " / ".join(said[n][:8]) for n in main)))
                pairing = {n: v for n, v in reply.items() if n in main and v in free}
                if len(set(pairing.values())) != len(pairing):
                    pairing = {}
            except (ValueError, json.JSONDecodeError):
                pairing = {}
        rest = [v for v in free if v not in pairing.values()]
        for n in main:
            cast[n]["voice"] = pairing.get(n) or rest.pop(0)
            changed = True
    return changed
