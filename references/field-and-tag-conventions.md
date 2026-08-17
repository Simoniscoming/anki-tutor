# 字段 / 标签 / 牌组约定

> 当你确定卡片字段、标签、归属牌组时读本文件。
> 这些约定让卡片库长期可维护、可检索、可统计。

---

## 字段

不同笔记类型用不同字段，**写入前用 `modelFieldNames` 确认实际字段名**，不要想当然。

| 笔记类型 | 字段 | 说明 |
|---|---|---|
| Basic | `Front` / `Back` | 正面问、背面答 |
| Cloze | `Text` / `Back Extra` | Text 里挖 `{{c1::...}}`，Back Extra 是补充 |
| Basic (and reversed) | `Front` / `Back` | 同 Basic，模型自动生成反向卡 |
| 图文卡 | 同 Basic 或 Cloze | 某字段嵌 `<img src="文件名">` |

⚠ **locale 坑（2026-08 实测）**：上表是英文 locale 的名字。**中文 locale 的全新库里没有 "Basic"/"Cloze"**——标准模型叫「问答题」（字段 `正面`/`背面`）和「填空题」（字段 `文字`/`背面额外`），`addNote modelName:"Basic"` 会直接报 `model was not found`。所以**模型名和字段名永远实查**（`modelNames` + `modelFieldNames`），写入、查重、诊断都别硬编码英文名。`scripts/anki_probe.py dedup` 的字段归一化已内置这套中英文兜底。

### 字段内容约定

- **支持 HTML**：字段内容会被当 HTML 渲染，可以加 `<b>`/`<i>`/`<br>`/`<img>`/`<code>`。
- **代码用围栏**：代码片段用 `<pre><code>...</code></pre>` 保留格式。
- **图片只写文件名**：`<img src="photo.png">`，文件本身用 `storeMediaFile` 传（见 image-input.md），不要嵌 base64。
- **字段要简洁**：Front 一句话，Back 尽量一句话答完。超长字段说明没拆好（回 card-principles.md 重拆）。

### 不要自定义新字段，除非用户明确要求

能用现有模型就用现有模型。需要自定义字段时，先用 `modelFieldNames` 查清楚，能加字段（`addModelField`）就别新建模型。

---

## 标签策略（三段式，全部可选）

标签用 `::` 分层（Anki 原生支持），形成树状结构。

### 1. 来源标签 `source::*`

标记卡片是从哪来的，便于追溯。

| 标签 | 含义 |
|---|---|
| `source::chat` | 聊天里贴的文本 |
| `source::image` | 从图片识别来的 |

### 2. 主题标签 `topic::*`

从内容推断的主题，kebab-case，支持嵌套。

```
topic::photosynthesis
topic::bio::cell-respiration
topic::python::decorator
topic::med::cardio::ecg
```

### 3. 元标签（可选）

只在特定情况下加：

- `needs-review`：拆卡理由弱、信息密度存疑，建议人工再核一遍。加了就在预览里告诉用户"X 张标了 needs-review，建议你重点看"。

### 不加的标签

- **不加难度标签**（`hard`/`easy`/`difficulty::*`）

为什么：难度应由真实复习数据（ease、间隔、答对率）决定，FSRS 算法会根据你的表现自动调整。AI 主观标的难度会污染调度——你以为简单的卡可能其实难，反之亦然。让数据说话，别让 AI 拍脑袋。

---

## 牌组归属

### 层级牌组（推荐）

Anki 用 `::` 分层，建议 `学科::主题::子主题`：

```
Biology::Photosynthesis
Programming::Python::Decorators
Medicine::Cardiology::ECG
```

层级牌组便于长期管理：可以在父牌组复习，也可以钻进子牌组精准复习。

### 默认牌组

| 情况 | 落点 |
|---|---|
| 用户明确指定 | 用用户的 |
| 用户没指定 | `Default::Inbox`（待整理区） |

**未指定牌组时，必须在预览里显著标注**："⚠ 未指定牌组，将进 Default::Inbox，确认时请指定目标牌组。"

为什么用 Inbox：避免新卡散落在 Default 根目录污染既有牌组。用户后续可以批量归档。

### 牌组不存在时

**先问用户要不要新建**，不要静默 `createDeck`。

```
预览阶段提示：牌组 "Biology::Photosynthesis" 不存在，要新建吗？
用户确认 → createDeck("Biology::Photosynthesis") → 写入
用户否决 → 落到 Default::Inbox
```

---

## 写入前的字段校验清单

调 `addNote`/`addNotes` 前，对每张卡确认：

- [ ] `deckName` 有值（或明确落 Inbox 并已告知用户）
- [ ] `modelName` 是 Anki 已有的（用 `modelNames` 核对）
- [ ] 字段名和该 model 一致（用 `modelFieldNames` 核对，别写错字段名）
- [ ] Cloze 卡的 `Text` 字段里至少有一个 `{{c1::...}}`
- [ ] 图文卡的 `<img>` 引用的文件已用 `storeMediaFile` 传过
- [ ] tags 数组里没有难度标签

校验不过就别写入，回预览让用户改。
