# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy", "soundfile"]
# ///
"""Builds the blind listening session: blind/session/index.html plus anonymised audio.

The letter -> engine mapping goes to blind/mapping.json (outside session/) and is only
read back by reveal.py, so the listening page itself never knows which engine is which.
"""
import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import common  # noqa: E402

HERE = Path(__file__).resolve().parent
SESSION = HERE / "session"

CATEGORY = {"passage": "长篇段落（约 6 分钟）"}


def main():
    engines = sorted(p.name for p in common.OUT.iterdir() if (p / "metrics.json").exists())
    main_set = [e for e in engines if "_x" not in e]
    speed_pairs = [(e.split("_x")[0], e) for e in engines if "_x" in e and e.split("_x")[0] in engines]

    rng = random.Random()
    letters = "ABCDEFGH"
    shuffled = rng.sample(main_set, len(main_set))
    mapping = {letters[i]: e for i, e in enumerate(shuffled)}

    shutil.rmtree(SESSION, ignore_errors=True)
    (SESSION / "audio").mkdir(parents=True)

    items = []
    texts = {}
    import csv
    with open(common.TEXTS / "cases.tsv", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            CATEGORY[row["id"]] = row["category"]
            texts[row["id"]] = row["text"]
    texts["passage"] = (common.TEXTS / "passage.txt").read_text(encoding="utf-8").strip()

    for item_id, _ in common.load_items():
        samples = []
        for letter, engine in mapping.items():
            src = common.OUT / engine / f"{item_id}.wav"
            if src.exists():
                dst = f"audio/{item_id}_{letter}.wav"
                shutil.copy(src, SESSION / dst)
                samples.append({"label": letter, "src": dst})
        items.append({"id": item_id, "category": CATEGORY[item_id], "text": texts[item_id], "samples": samples})

    # Native 2.5x synthesis vs 1x audio sped up at playback: same engine, labels X/Y shuffled.
    pairs = []
    for base, fast in speed_pairs:
        xy = rng.sample([("native", fast), ("playback", base)], 2)
        pair = {"id": f"speed_{base}", "samples": []}
        for label, (kind, engine) in zip("XY", xy):
            dst = f"audio/speed_{base}_{label}.wav"
            shutil.copy(common.OUT / engine / "passage.wav", SESSION / dst)
            pair["samples"].append({"label": label, "src": dst, "rate": 1.0 if kind == "native" else 2.5})
            mapping[f"{pair['id']}:{label}"] = kind
        pairs.append(pair)

    (HERE / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    page = (HERE / "template.html").read_text(encoding="utf-8")
    data = json.dumps({"items": items, "pairs": pairs, "letters": sorted(set(s["label"] for i in items for s in i["samples"]))},
                      ensure_ascii=False)
    (SESSION / "index.html").write_text(page.replace("/*DATA*/null", data), encoding="utf-8")
    print(f"{len(main_set)} engines blinded as {', '.join(sorted(mapping)[:len(main_set)])}; open {SESSION / 'index.html'}")


if __name__ == "__main__":
    main()
