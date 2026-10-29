"""IndexTTS-2 version of each comparison line: cloning the character's clip, with the emotion taken from the
director's tag and delivery direction (emo_alpha 0.6, the upstream advice for natural speech).

  cd ../vendor/index-tts && uv run python ../../emotion/gen_index.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINES = Path(__file__).parent / "lines"
sys.path.insert(0, str(ROOT / "vendor" / "index-tts"))
from indextts.infer_v2 import IndexTTS2  # noqa: E402

tts = IndexTTS2(cfg_path="checkpoints/config.yaml", model_dir="checkpoints", use_fp16=False)
voices = json.loads((ROOT / "refs" / "voices.json").read_text(encoding="utf-8"))
(LINES / "index_emo").mkdir(exist_ok=True)
for k, line in enumerate(json.loads((LINES / "lines.json").read_text(encoding="utf-8"))):
    out = LINES / "index_emo" / f"{k:02d}.wav"
    if out.exists():
        continue
    ref = voices[line["voice"]]["voice"].removeprefix("ref:")
    tts.infer(spk_audio_prompt=str(ROOT / "refs" / f"{ref}.wav"), text=line["line"],
              output_path=str(out),
              use_emo_text=True, emo_text=f"{line['emotion']}，{line['direction']}", emo_alpha=0.6)
    print(k, "done", flush=True)
