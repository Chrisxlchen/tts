"""Fun-CosyVoice3-0.5B (RL weights) cloning from the designed Reference Clip, official PyTorch code.

Runs in the CosyVoice repo's own venv (its pinned torch/transformers clash with the others):
  vendor/CosyVoice/.venv/bin/python engines/cosyvoice3.py [--device mps]
Upstream only knows CUDA or CPU; --device mps moves the loaded model to the Apple GPU afterwards.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "vendor" / "CosyVoice"
sys.path[:0] = [str(ROOT), str(REPO), str(REPO / "third_party" / "Matcha-TTS")]
import common  # noqa: E402

import torch  # noqa: E402

PROMPT_PREFIX = "You are a helpful assistant.<|endofprompt|>"


def build(model, ref, device):
    from cosyvoice.cli.cosyvoice import AutoModel

    tts = AutoModel(model_dir=str(ROOT / "models" / model))
    if device == "mps":
        m = tts.model
        m.device = torch.device("mps")
        m.llm.to(m.device)
        m.flow.to(m.device)
        # The vocoder's F0 predictor runs in float64, which MPS lacks, so the vocoder stays on CPU.
        hift_inference = m.hift.inference
        m.hift.inference = lambda speech_feat, **kw: tuple(
            t.to(m.device) for t in hift_inference(speech_feat=speech_feat.cpu(), **kw))
    ref_text = (ROOT / "refs" / f"{ref}.txt").read_text(encoding="utf-8").strip()
    assert tts.add_zero_shot_spk(PROMPT_PREFIX + ref_text, str(ROOT / "refs" / f"{ref}.wav"), ref)

    def synth(text):
        chunks = [j["tts_speech"] for j in tts.inference_zero_shot(text, "", "", zero_shot_spk_id=ref, stream=False)]
        return torch.cat(chunks, dim=1).squeeze(0).cpu().numpy(), tts.sample_rate

    return synth


if __name__ == "__main__":
    ap = common.cli(__doc__)
    ap.add_argument("--model", default="Fun-CosyVoice3-0.5B-RL")
    ap.add_argument("--ref", default="narrator_f")
    ap.add_argument("--device", default="cpu", choices=["cpu", "mps"])
    args = ap.parse_args()
    suffix = "" if args.device == "cpu" else f"_{args.device}"
    common.run(f"cosyvoice3_{args.ref}{suffix}", build(args.model, args.ref, args.device), only=args.only)
