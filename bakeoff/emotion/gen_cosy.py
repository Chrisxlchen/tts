"""CosyVoice3 versions of the comparison lines: plain cloning, and cloning plus the director's delivery direction.

  ../vendor/CosyVoice/.venv/bin/python gen_cosy.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engines"))
import cosyvoice3  # noqa: E402  (puts the CosyVoice repo on the path)

import soundfile as sf  # noqa: E402
import torch  # noqa: E402
from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402

LINES = Path(__file__).parent / "lines"
tts = AutoModel(model_dir=str(ROOT / "models" / "Fun-CosyVoice3-0.5B-RL"))
lines = json.loads((LINES / "lines.json").read_text(encoding="utf-8"))
voices = json.loads((ROOT / "refs" / "voices.json").read_text(encoding="utf-8"))
for k, line in enumerate(lines):
    ref = voices[line["voice"]]["voice"].removeprefix("ref:")
    wav = str(ROOT / "refs" / f"{ref}.wav")
    ref_text = (ROOT / "refs" / f"{ref}.txt").read_text(encoding="utf-8").strip()
    runs = {
        "cosy_plain": lambda: tts.inference_zero_shot(line["line"], cosyvoice3.PROMPT_PREFIX + ref_text, wav, stream=False),
        "cosy_instruct": lambda: tts.inference_instruct2(
            line["line"], f"You are a helpful assistant. 请用{line['emotion']}的语气说，{line['direction']}。<|endofprompt|>",
            wav, stream=False),
    }
    for name, run in runs.items():
        (LINES / name).mkdir(exist_ok=True)
        audio = torch.cat([j["tts_speech"] for j in run()], dim=1).squeeze(0).numpy()
        sf.write(LINES / name / f"{k:02d}.wav", audio, tts.sample_rate)
    print(k, "done", flush=True)
