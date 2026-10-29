"""IndexTTS-2 / 2.5 version of each comparison line: cloning the character's clip, with the emotion taken from
the director's tag and delivery direction (emo_alpha 0.6, the upstream advice for natural speech).

  cd ../vendor/index-tts && uv run python ../../emotion/gen_index.py [2|2.5]
IndexTTS-2 weights live in checkpoints/, 2.5 in checkpoints_25/.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINES = Path(__file__).parent / "lines"
sys.path.insert(0, str(ROOT / "vendor" / "index-tts"))

VERSION = sys.argv[1] if len(sys.argv) > 1 else "2"
if VERSION == "2.5":
    from indextts.infer_v2_5 import IndexTTS2  # noqa: E402

    tts = IndexTTS2(cfg_path="checkpoints_25/config.yaml", model_dir="checkpoints_25", use_qwen_emo=True)
    out_dir, extra = LINES / "index25_emo", {"lang": "ZH"}
else:
    from indextts.infer_v2 import IndexTTS2  # noqa: E402

    tts = IndexTTS2(cfg_path="checkpoints/config.yaml", model_dir="checkpoints", use_fp16=False)
    out_dir, extra = LINES / "index_emo", {}
voices = json.loads((ROOT / "refs" / "voices.json").read_text(encoding="utf-8"))
out_dir.mkdir(exist_ok=True)
for k, line in enumerate(json.loads((LINES / "lines.json").read_text(encoding="utf-8"))):
    out = out_dir / f"{k:02d}.wav"
    if out.exists():
        continue
    ref = voices[line["voice"]]["voice"].removeprefix("ref:")
    tts.infer(spk_audio_prompt=str(ROOT / "refs" / f"{ref}.wav"), text=line["line"], output_path=str(out),
              use_emo_text=True, emo_text=f"{line['emotion']}，{line['direction']}", emo_alpha=0.6, **extra)
    print(k, "done", flush=True)
