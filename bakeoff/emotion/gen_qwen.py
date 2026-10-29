"""The current pipeline's version of each comparison line: Qwen3-TTS Base cloning, no emotion.

  ~/.cache/uv/environments-v2/audiobook-*/bin/python gen_qwen.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "engines")]
import mlx_tts  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

LINES = Path(__file__).parent / "lines"
(LINES / "qwen_clone").mkdir(exist_ok=True)
say = mlx_tts.make_say()
for k, line in enumerate(json.loads((LINES / "lines.json").read_text(encoding="utf-8"))):
    audio, sr = say(line["line"], line["voice"])
    sf.write(LINES / "qwen_clone" / f"{k:02d}.wav", np.asarray(audio, np.float32).reshape(-1), sr)
