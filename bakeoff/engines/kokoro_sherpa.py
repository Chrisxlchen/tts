# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["sherpa-onnx>=1.12", "numpy", "soundfile"]
# ///
"""Kokoro v1.1-zh through sherpa-onnx (CPU, lexicon-based Chinese G2P)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common  # noqa: E402

import sherpa_onnx  # noqa: E402

MODEL = common.ROOT / "models" / "kokoro-multi-lang-v1_1"
# sherpa-onnx speaker ids for kokoro-multi-lang-v1_1 (see k2-fsa docs); only the Chinese voices we audition.
SPEAKERS = {"zf_001": 3, "zf_002": 4, "zf_003": 5, "zf_017": 11, "zf_022": 15, "zf_039": 24,
            "zm_009": 58, "zm_010": 59, "zm_014": 63, "zm_029": 68}


def build(voice, speed, threads):
    m = MODEL
    cfg = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                model=str(m / "model.onnx"),
                voices=str(m / "voices.bin"),
                tokens=str(m / "tokens.txt"),
                data_dir=str(m / "espeak-ng-data"),
                dict_dir=str(m / "dict"),
                lexicon=f"{m / 'lexicon-us-en.txt'},{m / 'lexicon-zh.txt'}",
            ),
            num_threads=threads,
            provider="cpu",
        ),
        rule_fsts=f"{m / 'phone-zh.fst'},{m / 'date-zh.fst'},{m / 'number-zh.fst'}",
        max_num_sentences=1,
    )
    tts = sherpa_onnx.OfflineTts(cfg)
    sid = SPEAKERS[voice]

    def synth(text):
        a = tts.generate(text, sid=sid, speed=speed)
        return a.samples, a.sample_rate

    return synth


if __name__ == "__main__":
    ap = common.cli(__doc__)
    ap.add_argument("--voice", default="zf_001", choices=sorted(SPEAKERS))
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--threads", type=int, default=os.cpu_count() // 2)
    args = ap.parse_args()
    name = f"kokoro_sherpa_{args.voice}" + ("" if args.speed == 1.0 else f"_x{args.speed:g}")
    common.run(name, build(args.voice, args.speed, args.threads), only=args.only)
