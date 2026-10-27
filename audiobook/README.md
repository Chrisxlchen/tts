# 整本书生成

在 Mac 上把无 DRM 的 EPUB（或带"第X章"标题的 .txt）生成有声书，导入 iPhone 的 BookPlayer 收听。

```bash
uv run --script audiobook.py list 书.epub                  # 看章节编号
uv run --script audiobook.py cast 书.epub --chapters 1-3   # 只分配角色，先检查 cast.json
caffeinate -i uv run --script audiobook.py build 书.epub   # 整本生成；caffeinate 防止合盖或睡眠中断
```

流程（每一步的结果都存在 `work/<文件名>/`，中断后重跑会接着做）：

1. **读入**：`book.json`（书名、作者、章节和段落）和封面。
2. **分配角色**：本地 Qwen3-30B-A3B 通读每章，判断每段引号里的台词是谁说的，并给新角色定性别和年龄段，换算成 Voice Type。
   - 模型会先思考再回答。思考最多 3000 个 token，超出就让它直接回答。思考能明显提高判断准确率；不加上限的话，一章要十几分钟。
   - 整本书都分配完后，再统计每个角色的台词量。台词多的主要角色会从同类型的变体音色里各分一个不同的，例如青年女有温柔、清冷、活泼、威仪四种，由大模型按台词判断性格来配。配角仍用该类型的基础音色。分配结果记在 `voices.assigned`，删掉这个文件可以重新分配。
   - 结果写入 `cast.json` 和 `speakers/`。
   - 叙述里明确写了"某某说"的，直接以文中写的为准，不采用模型的判断。
   - 可以手改 `cast.json`：把 `type` 改成另一种类型，或加 `"voice": "ref:<名字>"` 换成指定声音。改完删掉相应的 `chapters/*.m4a` 再重跑，只会重新生成受影响的片段。
3. **合成**：旁白用 Narrator Voice（平稳风格），引号内的台词用说话角色的 Character Voice。
   - 每段声音都统一到 -20 dBFS 响度，旁白和对白之间不会忽大忽小。
   - 每个 Segment 都用 SenseVoice 回听，按不带声调的拼音比对，所以识别器写成同音字（她/他、师父/师傅）不算读错。音节错误率超过 10% 就重新生成，最多 3 次，取最好的一次。
   - 生成好的片段缓存在 `seg/`。
4. **导出**：每章一个 `chapters/NNN 标题.m4a`，生成一章就能先导入 BookPlayer 收听；全部章节完成后再合成一个带章节标记的 `<书名>.m4b`。
   - `report.json` 记录每章的生成速度、重试次数，以及重试后仍未过关的片段。

声音库（旁白 + 10 种 Voice Type）在 `../bakeoff/refs/voices.json`，分段和回听代码与 `../bakeoff` 共用。

`samples/回乡.epub` 是一本两章的原创测试书，由 `samples/make_sample.py` 生成。
