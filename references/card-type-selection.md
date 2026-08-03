# 卡片类型选择：Basic / Cloze / 双向 / 图文

> 当你要决定一张卡用什么类型时读本文件。
> Anki 的"笔记类型（model）"决定了一张卡长什么样、有几面。

## 目录

- 四种核心类型 ........................ 见下文「四种类型」
- 决策树 ................................ 见下文「决策树」
- 场景速查表 ............................ 见下文「场景速查」
- Input/Output 示例 ..................... 见下文「示例」
- 关键约束 .............................. 见下文「关键约束」

---

## 四种类型

### 1. Basic（基础问答）

- 字段：`Front` / `Back`
- 一张卡，正面问、背面答
- 适合：明确的一问一答、概念定义、代码

### 2. Cloze（填空）

- 字段：`Text` / `Back Extra`
- 在 `Text` 里用 `{{c1::被挖的内容}}` 挖空
- 一段话里挖多个空会自动生成多张卡（c1、c2、c3...）
- 适合：定义里挖关键术语、公式挖变量、句子挖核心词

### 3. Basic (and reversed card)（双向）

- 字段同 Basic：`Front` / `Back`
- 模型自动生成两张卡：正向（Front→Back）+ 反向（Back→Front）
- 适合：双向关系（术语↔定义、国家↔首都、单词↔释义）

### 4. 图文卡（图片嵌入）

- 字段同 Basic 或 Cloze，只是某个字段里嵌入了 `<img src="文件名">`
- 不是独立模型，而是给 Basic/Cloze 的字段加图
- 适合：解剖图、流程图、示意图、公式截图——Front 问"这是什么"，Back 放图；或反过来 Front 放图问名称

> 图片怎么传进 Anki 见 `image-input.md`。

---

## 决策树

```
这张卡的知识点是什么形态？
│
├─ 是"一段定义/句子，关键是其中某个词"
│  → Cloze（挖空那个关键术语）
│
├─ 是"两个东西互为对应"（A↔B）
│  → Basic (and reversed)
│
├─ 是代码 / 命令 / 有固定语法的表达式
│  → Basic（绝对不用 Cloze！挖空会破坏语法）
│
├─ 需要图片来呈现答案（图、图示、截图）
│  → 图文卡（Basic + 字段嵌 <img>）
│
├─ 是"问一个问题，答案是说明/解释"
│  → Basic
│
└─ 不确定
   → 默认 Basic（最通用）
```

---

## 场景速查

| 内容形态 | 推荐类型 | 原因 |
|---|---|---|
| 术语定义（挖关键词）| Cloze | 在语境中回忆，比孤立 Q&A 牢 |
| 术语↔释义（双向）| Basic (rev) | 避免方向依赖 |
| 国家↔首都、单词↔中文 | Basic (rev) | 双向关系 |
| 代码片段、命令行 | Basic | 不能挖空破坏语法 |
| 流程的某一步 | Basic | 单点问 |
| 对比表的某一行 | Basic (rev) | 双向互查 |
| 公式里的变量 | Cloze | 挖变量名 |
| 解剖图/示意图/流程图 | 图文卡 | 图本身就是答案 |
| 一句完整陈述的核心信息 | Cloze | 多个挖空 = 多张卡 |

---

## 示例

### 例 1：定义 → Cloze

```
原文：光合作用把光能转化为化学能，储存在葡萄糖中。

✅ 选 Cloze
   Text: 光合作用把光能转化为{{c1::化学能}}，储存在{{c2::葡萄糖}}中。
   （自动生成 2 张卡：分别挖化学能、挖葡萄糖）
```

### 例 2：双向关系 → Basic (reversed)

```
原文：Photosynthesis = 光合作用

✅ 选 Basic (and reversed)
   Front: Photosynthesis
   Back: 光合作用
   （自动生成 2 张：英→中、中→英）
```

### 例 3：代码 → Basic（不用 Cloze）

```
原文：Python 里 `@decorator` 等价于 `func = decorator(func)`

✅ 选 Basic
   Front: Python 中 `@decorator` 写在函数定义上方，等价于什么？
   Back: func = decorator(func)

❌ 错误：用 Cloze 挖空 `decorator` 或 `func` —— 会破坏代码语法，让卡片看不懂
```

### 例 4：流程单点 → Basic

```
原文：TCP 三次握手后连接进入 ESTABLISHED 状态。

✅ 选 Basic
   Front: TCP 三次握手完成后，连接处于什么状态？
   Back: ESTABLISHED
```

### 例 5：对比 → Basic (reversed)

```
原文：TCP 面向连接、可靠；UDP 无连接、不可靠。

✅ 拆成多张 Basic (rev)
   Front: 哪种传输层协议是面向连接的？→ TCP
   Front: 哪种传输层协议是无连接的？→ UDP
   （双向：也能从 TCP/UDP 反问特征）
```

### 例 6：示意图 → 图文卡

```
场景：用户给了一张心脏解剖图，图上有"左心房/左心室/右心房/右心室"等标注。

✅ 选 Basic 图文卡
   Front: <img src="heart_anatomy.png">
   Back: 心脏解剖图（左心房/左心室/右心房/右心室...）
   
   或者反过来：Front 问"心脏四个腔室是什么"，Back 放图 + 文字。

注意：图片要先用 storeMediaFile 传进 Anki（见 image-input.md），
字段里只写文件名 <img src="heart_anatomy.png">。
```

---

## 关键约束

- **代码绝不用 Cloze**：挖空 `{{c1::xxx}}` 会插入额外字符，破坏代码语法和缩进。
- **Cloze 的 Text 必须是完整句子**：不能只写一个词然后挖空，那样失去语境。
- **一张卡只选一种类型**：不要在 Basic 卡里塞填空逻辑。
- **图文卡的图先用 storeMediaFile 传**：字段里只引用文件名，不嵌 base64。
- **优先用 Anki 自带模型**：Basic / Cloze / Basic (and reversed) 是 Anki 默认就有的，不需要 `createModel`。只有特殊需求才新建模型。
