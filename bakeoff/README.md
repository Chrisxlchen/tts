# 中文 TTS 盲听对比（第一阶段）

在 M3 Pro 上比较几个中文 TTS 引擎的音质、速度和长文本稳定性，用来决定走"Mac 生成 → BookPlayer 播放"还是"iPhone 本地生成"。

```bash
./run_all.sh                      # 每个引擎依次合成全部测试文本，然后用 SenseVoice 回听并计算错字率
uv run --script blind/build.py    # 打乱成 A/B/C… 生成 blind/session/index.html
open blind/session/index.html     # 盲听打分，最后点"导出评分"
python3 blind/reveal.py           # 揭晓，生成 RESULTS.md
```

- `texts/`：测试用例（声调变调、多音字、中英混排、数字、对白）和一段约 6 分钟的原创小说片段。
- `engines/`：每个引擎一个脚本（uv 内联依赖），只负责 `synth(text)`；切段、计时和输出由 `common.py` 统一处理。
- `asr/score.py`：逐个 Segment 回听，错字率超过 10% 记为"需重试"。
- `refs/`：用 VoxCPM2 按文字描述设计出来的 Reference Clip（合成声音，不是真人）。
- `vendor/`：需要从源码运行的两个引擎（不进 git）。
  - FluidAudio：`git clone https://github.com/FluidInference/FluidAudio` 后执行 `swift build -c release --product fluidaudiocli`。
  - CosyVoice：`git clone --recursive https://github.com/FunAudioLLM/CosyVoice`，在仓库里建 Python 3.10 的 `.venv`，按 `requirements.txt` 安装，但要去掉 CUDA/Linux 专用包，并把 openai-whisper 换成 20250625 版。模型放在 `models/Fun-CosyVoice3-0.5B`；`models/Fun-CosyVoice3-0.5B-RL` 里用软链接把 `llm.pt` 指向 `llm.rl.pt`，即 RL 版权重。
- 模型下载到 `models/` 和 `~/.cache/huggingface`，不进 git。
