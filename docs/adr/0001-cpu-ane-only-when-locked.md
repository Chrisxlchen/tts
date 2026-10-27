# 锁屏推理只用 CPU/ANE，切换计算设备不得改变声音

iOS 会拒绝后台 App 提交 GPU 命令（Metal 返回 `notPermitted`），而本 App 要求锁屏后边播边预生成，所以锁屏时的推理只能跑在 CPU 或神经网络引擎（ANE）上。因此放弃了原本首选的 MLX 路线（kokoro-ios / kokoro-swift，纯 GPU，且只支持英文 G2P）。前台亮屏时允许用 GPU 加速，但同一章节的音频必须来自同一个模型和同一个音色，计算设备只影响速度，不影响声音。

## Consequences

- 不能为了音质在前台换用只能跑在 GPU 上的大模型，否则锁屏后同一章的声音会变化。
- Core ML 必须显式设置 `.cpuOnly` 或 `.cpuAndNeuralEngine` 才能在锁屏时使用。FluidAudio 默认路线含有 GPU 阶段，需要改掉。
- Core ML 在后台跑 ANE 没有 Apple 官方保证，开发者论坛有 iOS 27 beta 出现回归的报告，所以每次系统大版本升级都要重测锁屏生成。
