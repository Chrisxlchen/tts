#!/bin/zsh
# Renders every test item with every runnable engine, then ASR-scores them.
# One engine at a time so speed numbers are not skewed by contention.
set -e
cd "${0:A:h}"
rm -rf out/*

uv run --script engines/kokoro_sherpa.py --voice zf_001
uv run --script engines/kokoro_sherpa.py --voice zf_001 --speed 2.5
uv run --script engines/mlx_tts.py qwen3 --speaker Vivian
uv run --script engines/mlx_tts.py voxcpm2 --ref narrator_f --quant 8bit
uv run --script engines/kokoro_fluid.py --voice zf_001   # needs: swift build -c release in vendor/FluidAudio
PYTORCH_ENABLE_MPS_FALLBACK=1 vendor/CosyVoice/.venv/bin/python engines/cosyvoice3.py --device mps

uv run --script asr/score.py $(ls out)
