"""Voices Acted Lines with IndexTTS-2: reads <acted>/jobs.json, writes <acted>/<key>.wav for each missing one.

Runs inside IndexTTS-2's own venv (see acting.act): cd ../bakeoff/vendor/index-tts && uv run python <this> <acted dir>
The emotion comes from the director's tag and delivery direction; emo_alpha 0.6 is upstream's advice for
natural speech, and what the blind test used.
"""
import json
import sys
import time
from pathlib import Path

from indextts.infer_v2 import IndexTTS2

acted = Path(sys.argv[1])
todo = [j for j in json.loads((acted / "jobs.json").read_text(encoding="utf-8")) if not (acted / f"{j['key']}.wav").exists()]
tts = IndexTTS2(cfg_path="checkpoints/config.yaml", model_dir="checkpoints", use_fp16=False)
t0 = time.perf_counter()
for i, j in enumerate(todo, 1):
    tmp = acted / f"{j['key']}.tmp.wav"  # renamed when complete, so an interrupted line is redone
    tts.infer(spk_audio_prompt=j["ref"], text=j["text"], output_path=str(tmp),
              use_emo_text=True, emo_text=f"{j['emotion']}，{j['direction']}", emo_alpha=0.6)
    tmp.rename(acted / f"{j['key']}.wav")
    left = (time.perf_counter() - t0) / i * (len(todo) - i)
    print(f"[act] {i}/{len(todo)} done, about {left / 60:.0f} min left", flush=True)
