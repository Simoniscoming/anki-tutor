---
name: anki-cards
version: 0.1.0
description: 把文本/笔记/代码/公式/图片拆成高质量 Anki 闪卡并写入 Anki。当用户说"做成 anki 卡片""加进 anki""做个 flashcard""帮我背这个""这段老记不住""这个会考""记到 anki 里""make anki cards""turn this into flashcards"时使用。即使用户没直接说"anki"或"卡片"，只要流露出明确的记忆意图——比如贴代码/公式/术语说"老是忘""怕忘""考试要考""想记牢"——也触发。贴文本默认走拆卡流程，支持自然语言（"光合作用的反应物"→自动拆卡）。不负责纯复习调度、删卡、Anki 报错排查。
---

# Anki 制卡助手

把用户贴的学习内容拆成高质量的原子闪卡，预览确认后写入 Anki。

这个 Skill 的核心信念是：**Anki 是记一辈子的库，AI 任何一处幻觉都会把错误信息刻进用户大脑。** 所以宁可慢一步（先预览、先查重、先等确认），也不要图快批量直写。

## 何时使用

- 用户贴一段文本/笔记/概念，想要做成 Anki 卡片
- 用户说"这段记不住""帮我背一下""拆成卡片""我想记到 anki"
- 用户给了中英混合内容，要拆成可复习的卡片
- **用户提供图片**（截图、图表、手写笔记、示意图、公式照片），想把图嵌进卡片或从图识别内容制卡

即使用户没明说"制卡"，只要意图是"把这段内容固化成可复习的知识点"，也应触发。

## 何时不使用（交给别的工具，别抢活）

- 纯查现有卡 → 直接用 anki-mcp 的 `findNotes`/`notesInfo`，不必走本 Skill 的拆卡流程
- 纯复习/调度 → 不是本 Skill 职责（未来可能有 anki-review）
- 删卡 → 直接用 `deleteNotes`（注意它需 `confirmDeletion: true`）
- Anki 本身报错、AnkiConnect 连不上 → 排障，不是制卡

## 前置条件

每次制卡前确认这三项，缺一不可：

1. **Anki 桌面端正在运行**（不是手机版，不是 AnkiWeb 网页）
2. **AnkiConnect 插件已启用**（默认监听 `http://localhost:8765`）
3. **anki-mcp 已加载**（项目 `.mcp.json` 里配置的 MCP server）

如果调 MCP 工具时报连接错误，**先让用户检查 Anki 是否开着**，而不是盲目重试——99% 的连接失败都是 Anki 没开。

## 核心工作流

按这个顺序走，每个节点都对应一个规则文件，用到时才读（渐进式披露）：

```
用户贴文本 / 提供图片
   │
   ├─ 涉及图片 ──► 读 references/image-input.md，默认走两条全自动路径：
   │     ① 图文嵌入卡（图当答案）→ storeMediaFile 传图 + 字段写 <img>，进下方流程
   │     ② 图片作制卡输入 → 多模态识别转文本，再走下方文本流程
   │     （Image Occlusion 因每次需用户手动操作、体验差，非必要不推荐，
   │      详见 image-input.md，待将来有全自动方案再解除限制）
   │
   ▼
① 理解内容 + 推断牌组/笔记类型
   │   （用户没指定时，按 field-and-tag-conventions.md 推断，
   │    但要在预览里告知"我推断成 X，不对请说"）
   │
   ▼
② 按法则拆成原子卡 ──► 必读 references/card-principles.md
   │   选卡片类型 ──► 读 references/card-type-selection.md
   │   拆完看张数：
   │     > 40 张 → 按 card-principles.md 的总量阈值先问"精简 vs 继续"
   │              （别默认减量，也别默认全灌）
   │     > 20 张 → 走分批预览（preview-format.md）
   │
   ▼
③ 查重 ──► 读 references/dedup-strategy.md
   │   （对每张卡跑 findNotes，命中则标 ⚠ 给用户决定）
   │
   ▼
④ 生成预览（markdown 表格）──► 读 references/preview-format.md
   │
   ▼
⑤ ⏸ 等待用户确认   ◄── 红线：未确认绝不调 addNote/addNotes
   │
   ▼
⑥ 写入 Anki
   │   ≤100 张 → addNotes 批量
   │   单张 → addNote
   │   >100 张 → 分批，串行（不要并发）
   │
   ▼
⑦ 报告结果（成功 N / 失败 M / 跳过 K）
```

**每个节点的 why**：

- ② 拆卡质量决定一切。Wozniak 法则是 SuperMemo 创始人几十年研究沉淀的制卡黄金标准，遵守它能从源头避免"记了一堆废卡"。详见 card-principles.md。
- ③ 查重是为了不重复造轮子。同一知识点复习两次，既浪费也打乱 FSRS 调度算法。
- ⑤ 等确认是防幻觉的最后一道关。AI 拆的卡可能有错或质量低，用户看一眼能拦下大部分问题。这道关不能省。

## 快速路由表

| 用户场景 | 优先动作 | 何时读 reference |
|---|---|---|
| 贴文本要拆卡 | 走完整工作流 ①→⑦ | card-principles.md |
| 贴了长文本/整章，拆卡后偏多 | >40 张先问精简 vs 继续；>20 张分批预览 | card-principles.md（总量阈值）+ preview-format.md（分批预览） |
| 用户指定了牌组/类型 | 跳过推断，直接用用户指定 | field-and-tag-conventions.md |
| 文本里有定义/填空 | 优先 Cloze | card-type-selection.md |
| 文本是流程/对比/列表 | 优先双向 Basic | card-type-selection.md |
| 文本是代码 | 用 Basic，别用 Cloze（会破坏语法） | card-type-selection.md |
| 担心重复 | 写入前 findNotes 查 | dedup-strategy.md |
| 用户要改预览 | 按指令语法重生成，再等确认 | preview-format.md |
| 图当卡片答案（解剖图/示意图等） | 图文嵌入：storeMediaFile 传图 + 字段写 `<img>` | image-input.md（路径A） |
| 图是制卡原料（教材照片/截图） | 多模态识别转文本，再走拆卡 | image-input.md（路径B） |
| 想要图片遮挡（Image Occlusion） | 非必要不推荐，说明现状并引导用插件 | image-input.md（路径C） |

## 防护红线

这四条针对 AI 制卡最容易翻车的坑。每条都有明确的 why，理解了 why，边界情况下你也能自己判断。

### 1. 预览确认制——未确认前只生成不写入

拆完卡必须先以表格预览，等用户明确说"OK/写入/确认"后才调 addNote。

为什么：Anki 是记一辈子的库。AI 一旦幻觉出错卡并写入，用户复习时就会把错误信息刻进脑子，比不学还糟。这是 Reddit Anki 社区的最高赞共识。预览这一步是拦住错误卡的最后机会。

即使用户说"直接写别问"，也要给一个极简预览（哪怕两三行），但可以缩短流程："预览如上，你说 OK 我就写"。不要完全跳过预览。

### 2. 不做低质量批量——拆不出就主动减量

一段文本如果拆不出 5 张以上有意义的卡，不要硬凑数量。主动减量并告诉用户"这几条信息密度不够，建议合并或丢弃"。

为什么：新手最大的陷阱就是盲目堆量，产出一堆低质量废卡，复习时浪费时间还打击信心。宁可少而精，不要多而滥。质量判断标准见 card-principles.md。

### 3. 写入前查重

每张卡写入前，对 Front 提取关键词跑 `findNotes` 搜目标牌组，命中相似的要在预览里标 `⚠ 与现有卡 #ID 相似`，让用户决定跳过/更新/仍新建。

为什么：重复卡让同一知识点被复习多次，浪费且打乱 FSRS 调度。社区共识是"宁可漏不可重"。查重方法见 dedup-strategy.md。

### 4. 改卡前提醒用户关掉 Anki 浏览器

如果要用 `updateNoteFields` 修改已有卡片，先提醒用户："如果你正在 Anki 浏览器里查看这张卡，请先关掉或切到别的卡。"

为什么：这是 AnkiConnect 的上游 bug——同时浏览和修改同一张卡会导致修改静默失败（不报错但没生效）。v1 主要做新建卡，这条主要为以后的改卡功能预留，但先养成提醒的习惯。

## 字段/标签/牌组默认

详细约定见 `references/field-and-tag-conventions.md`，这里给硬默认：

- **字段**：Basic 用 `Front`/`Back`；Cloze 用 `Text`/`Back Extra`；双向卡用 Basic 的 `Front`/`Back`（模型自动生成反向）。
- **标签**（三段式，全可选）：
  - 来源：`source::chat`（聊天贴的）
  - 主题：`topic::<推断主题>`，如 `topic::photosynthesis`，支持嵌套 `topic::bio::cell`
  - 待复核：`needs-review`（拆卡理由弱、建议人工再看的）
  - **不加难度标签**（hard/easy）——难度应由真实复习数据（ease、间隔）决定，AI 主观标难度会污染 FSRS 调度
- **牌组**：用户指定就用用户的；没指定就默认 `Default::Inbox`（待整理区），并在预览里显著标注"⚠ 未指定牌组，将进 Default::Inbox"。

## 写入与报告

### 写入

- 用 `addNotes` 批量写入，单批最多 100 张；超过分批，串行执行（AnkiConnect 不适合并发）。
- 单张卡用 `addNote`。
- 写入前如果牌组/模型不存在，**先问用户要不要新建**，不要静默创建。

### 报告格式

```
✓ 成功 N 张 → <牌组名>
✗ 失败 M 张：<原因列表>
⏭ 跳过 K 张（重复 / 用户要求）
```

### 常见失败与恢复

| 失败原因 | 怎么恢复 |
|---|---|
| 字段名不对（如 Basic 没有 Text 字段） | 用 `modelFieldNames` 重新查该模型的字段 |
| 牌组不存在 | 问用户后 `createDeck` 再重试 |
| 模型不存在 | 用 `modelNames` 核对，或问用户用哪个 |
| 连接失败 | 让用户检查 Anki 是否开着 |

## 未来扩展（v1 不实现，但结构已预留）

以下三个方向目前不实现，但 References 结构已留接口，未来加对应文件即可：

- **文件路径输入**：读本地 md/txt/pdf/docx 制卡（未来加 `references/file-input.md`）
- **主题生成**：针对某主题基于 AI 自身知识生成卡片（未来加 `references/topic-generation.md`）
- **改进现有卡片**：从已有牌组找卡来拆分/优化（未来加 `references/improve-existing.md`）
