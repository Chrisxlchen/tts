# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy", "soundfile"]
# ///
"""Kokoro v1.1-zh through FluidAudio's Core ML port (misaki[zh]-style G2P), via its CLI.

The CLI is spawned once per Segment, so measured speed includes model loading and
understates what an in-process integration (the iPhone app) would get.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common  # noqa: E402

import soundfile as sf  # noqa: E402

CLI = common.ROOT / "vendor/FluidAudio/.build/out/Products/Release/fluidaudiocli"


def build(voice):
    tmp = Path(tempfile.mkdtemp())

    def synth(text):
        out = tmp / "seg.wav"
        subprocess.run([str(CLI), "tts", text, "--backend", "kokoro-ane", "--kokoro-version", "v3",
                        "--variant", "zh", "--voice", voice, "--output", str(out)],
                       check=True, capture_output=True)
        audio, sr = sf.read(out, dtype="float32")
        return audio, sr

    return synth


if __name__ == "__main__":
    ap = common.cli(__doc__)
    ap.add_argument("--voice", default="zf_001")
    args = ap.parse_args()
    common.run(f"kokoro_fluid_{args.voice}", build(args.voice), only=args.only)
