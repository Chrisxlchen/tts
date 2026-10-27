# 离线听书

一个个人用 iPhone App：把无 DRM 的电子书在本机转换成语音并连续播放，不依赖任何服务器。

## Language

**Book（书）**:
用户导入的一本无 DRM 电子书（EPUB）或一段粘贴文本，是听书进度与设置的归属单位。
_Avoid_: 文档, 文件

**Book Language（书籍语言）**:
一本 Book 被指定的唯一朗读语言（中文或英文），决定可选的音色；书中夹杂的少量另一语言文字仍按书籍语言的音色朗读。
_Avoid_: 语种, locale

**Chapter（章节）**:
Book 内的一个阅读与预生成单位，对应电子书目录中的一节。
_Avoid_: section, 部分

**Voice（音色）**:
一个可选的朗读声音，属于且仅属于一种语言。
_Avoid_: speaker, 声音模型

**Segment（朗读片段）**:
Chapter 中被一次合成的一小段文字，带有自己的 Voice；是预生成、播放定位和日后分配角色音色的最小单位。
_Avoid_: chunk, 句子, utterance

**Narrator Voice（旁白音色）**:
一本 Book 选定的默认 Voice，朗读所有未分配给角色的文字。
_Avoid_: 默认声音

**Character Voice（角色音色）**:
分配给书中某个说话角色的 Voice，用于朗读该角色引号内的对白；主要角色在整本 Book 中保持同一个 Character Voice，从与其 Voice Type 相符的 Voice 中选出。
_Avoid_: 配音

**Voice Type（音色类型）**:
按年龄段（老年、中年、青年、少年、儿童）和性别划分的角色类别，共十种；声音库为每种 Voice Type 准备 Voice，Narrator Voice 不属于任何 Voice Type。
_Avoid_: 角色类型, archetype

**Reference Clip（参考录音）**:
一段 5–15 秒的录音，用来让模型模仿出一个 Voice；可以是许可明确或本人同意的真人录音，也可以是按文字描述合成出来的声音，不模仿真实的商业主播。
_Avoid_: 样本, prompt audio

**Pronunciation Fix（发音纠错）**:
一条"某个词应读作某个读音"的规则，分全局和单本 Book 两级，用来纠正多音字、人名等读错的地方。
_Avoid_: 词典, lexicon

**Playback Speed（播放倍速）**:
用户收听时选择的倍速（例如 2.5×）。
_Avoid_: 语速, speed

**Pre-generation（预生成）**:
在用户听到之前，提前把后续文字转换成音频并保存的过程。
_Avoid_: 缓冲, 预加载, prefetch
