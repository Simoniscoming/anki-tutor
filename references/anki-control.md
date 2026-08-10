# 用 curl 控制 Anki（AnkiConnect 接口指南）

> 本 Skill 不依赖外部 MCP。所有与 Anki 的交互都通过 **AnkiConnect 插件的 HTTP 接口**（`POST http://localhost:8765`，JSON-RPC）直接用 curl 调用。
> 本文件是这些调用的**操作手册**：哪些 action 能用、curl 模板、已知坑、FSRS 能力边界。

## 目录

- 前置条件 ............................... 见下文「前置」
- 连通性自检 ............................. 见下文「自检」
- 已验证 action 白名单 ................... 见下文「白名单」
- curl 模板（读写卡/配置/统计）.......... 见下文「模板」
- 三个必须防御的坑 ....................... 见下文「三坑」
- FSRS 能力边界 ......................... 见下文「FSRS 边界」
- 评估学习计划的数据来源 ................. 见下文「学习计划数据」

---

## 前置

每次调用 AnkiConnect 前，确认：

1. **Anki 桌面端正在运行**（不是手机版、不是 AnkiWeb 网页）
2. **AnkiConnect 插件已安装并启用**（默认监听 `http://localhost:8765`）
3. **没有其他进程抢占 8765 端口**

调 curl 时如果连接失败，**99% 是 Anki 没开**。先让用户检查 Anki，不要盲目重试。

---

## 自检

第一步永远先跑这个，确认连通性：

```bash
curl -s -X POST http://localhost:8765 -d '{"action":"version","version":6}'
# 期望：{"result": 6, "error": null}
```

拿到 `{"result":6,...}` 才继续。拿到连接错误就停下来排障。

---

## 白名单

> **分类说明（两类标记）**：
> - **✅** = 已在本机实测往返成功，可放心调用
> - **🟡** = AnkiConnect 源码里确认存在，但**尚未在本机实测**。首次调用要预期可能行为与文档描述有出入；**验证完后请删掉该行的 `<!-- unchecked -->` 标记。**
> - 源码全集 grep 自 `addons21/2055492159/__init__.py`（123 个 action）。
>
> ⚠️ **不在下表的 action 不要调**——源码里没有的就是 `unsupported action`。

### 卡片（Card）

| action | 用途 | 返回要点 |
|---|---|---|
| ✅ `findCards` | 按 query 搜卡片 | cardId 数组 |
| ✅ `cardsInfo` | 取卡片详情（含调度数据） | 含 interval、reps、lapses、**nextReviews** |
| ✅ `getIntervals` | 卡片未来间隔预测 | 如 `[10分, 12天, 30天, 1.3月]` |
| ✅ `getEaseFactors` / `setEaseFactors` | 读/写难度因子 | 整数数组 |
| 🟡 `cardsToNotes` <!-- unchecked --> | cardId → noteId | noteId 数组 |
| 🟡 `cardsModTime` <!-- unchecked --> | 卡片修改时间 | — |
| 🟡 `setSpecificValueOfCard` <!-- unchecked --> | 设卡片特定字段值 | — |
| 🟡 `suspend` / `unsuspend` <!-- unchecked --> | 挂起 / 恢复卡片（调控计划） | — |
| 🟡 `suspended` / `areSuspended` <!-- unchecked --> | 查挂起状态 | bool |
| 🟡 `areDue` <!-- unchecked --> | 查是否到期 | bool |
| 🟡 `setDueDate` <!-- unchecked --> | **改卡片到期日（直接调计划）** | — |
| 🟡 `forgetCards` <!-- unchecked --> | 重置为新卡（重学） | — |
| 🟡 `relearnCards` <!-- unchecked --> | 置为 relearning | — |
| 🟡 `answerCards` <!-- unchecked --> | 程序化答题（影响 FSRS 调度，**慎用**） | — |

### 笔记（Note）

| action | 用途 | 返回要点 |
|---|---|---|
| ✅ `addNote` | 建单张 | noteId |
| ✅ `addNotes` | 批量建（≤100/批） | noteId 数组 |
| ✅ `findNotes` | 按 query 搜笔记（查重用） | noteId 数组 |
| ✅ `notesInfo` | 取笔记详情（字段/标签/模型） | 含 fields、tags、modelName |
| ✅ `updateNoteFields` | 改笔记字段 | true/false |
| ✅ `deleteNotes` | 删笔记（**需 confirmDeletion:true**） | — |
| 🟡 `canAddNotes` <!-- unchecked --> | 预检：能否加卡 | bool 数组 |
| 🟡 `canAddNotesWithErrorDetail` <!-- unchecked --> | 预检 + 错误详情（更推荐） | — |
| 🟡 `updateNote` <!-- unchecked --> | 改字段+标签（比 updateNoteFields 全） | — |
| 🟡 `updateNoteModel` <!-- unchecked --> | 改笔记的 model | — |
| 🟡 `getNoteTags` / `updateNoteTags` <!-- unchecked --> | 读/改单卡标签 | — |
| 🟡 `notesModTime` <!-- unchecked --> | 笔记修改时间 | — |
| 🟡 `removeEmptyNotes` <!-- unchecked --> | 删空笔记 | — |

### 牌组（Deck）

| action | 用途 | 返回要点 |
|---|---|---|
| ✅ `deckNames` | 列所有牌组 | 牌组名数组 |
| ✅ `createDeck` | 建牌组（**addNote 前必须先建**） | deckId |
| ✅ `changeDeck` | 移动卡片到别的牌组 | — |
| ✅ `getDeckConfig` | **读牌组配置（含全部 FSRS 字段）** | 完整 config 对象 |
| ✅ `saveDeckConfig` | **写牌组配置（传完整对象）** | true/false |
| ✅ `cloneDeckConfigId` | 克隆配置组 | 新 configId |
| ✅ `removeDeckConfigId` | 删配置组 | — |
| ✅ `getDeckStats` | 每牌组的 new/learn/review 计数 | 按 deckId 分组 |
| 🟡 `deckNamesAndIds` <!-- unchecked --> | 牌组名 + ID（比 deckNames 更全） | — |
| 🟡 `deckNameFromId` <!-- unchecked --> | deckId → name | — |
| 🟡 `getDecks` <!-- unchecked --> | 查 cardId 属于哪些 deck | — |
| ✅ `deleteDecks` | 删牌组（**Anki 2.1.28+ 强制 cardsToo:true**） | — |
| 🟡 `setDeckConfigId` <!-- unchecked --> | 给牌组换配置组 | — |

### 模型/模板（Model）

| action | 用途 |
|---|---|
| ✅ `modelNames` | 列所有笔记类型 |
| ✅ `modelFieldNames` | 取某类型字段名（写入前必查） |
| ✅ `createModel` | 建新笔记类型 |
| 🟡 `modelNamesAndIds` <!-- unchecked --> | 模型名 + ID |
| 🟡 `modelNameFromId` <!-- unchecked --> | modelId → name |
| 🟡 `findModelsById` / `findModelsByName` <!-- unchecked --> | 按 ID/名查模型详情 |
| 🟡 `modelTemplates` / `modelStyling` <!-- unchecked --> | 读模板/CSS |
| 🟡 `updateModelTemplates` / `updateModelStyling` <!-- unchecked --> | 改模板/CSS |
| 🟡 `modelFieldAdd/Remove/Rename/Reposition` <!-- unchecked --> | 字段增删改序 |
| 🟡 `modelFieldSetFont` / `modelFieldSetFontSize` <!-- unchecked --> | 字段字体/字号 |
| 🟡 `modelFieldDescriptions` / `modelFieldSetDescription` <!-- unchecked --> | 字段描述 |
| 🟡 `modelTemplateAdd/Remove/Rename/Reposition` <!-- unchecked --> | 模板增删改序 |
| 🟡 `findAndReplaceInModels` <!-- unchecked --> | 模型内查找替换 |

### 标签（Tag）

| action | 用途 |
|---|---|
| ✅ `getTags` | 列所有标签 |
| ✅ `addTags` / `removeTags` | 加/删标签 |
| ✅ `replaceTags` | 重命名标签 |
| 🟡 `replaceTagsInAllNotes` <!-- unchecked --> | 全库重命名标签 |
| 🟡 `clearUnusedTags` <!-- unchecked --> | 清理未使用标签 |

### 媒体（Media）

| action | 用途 |
|---|---|
| ✅ `storeMediaFile` | 传图到 collection.media（**优先用本地路径/URL，避免 base64**） |
| ✅ `retrieveMediaFile` / `getMediaFilesNames` | 取媒体 |
| ✅ `deleteMediaFile` | 删媒体 |
| 🟡 `getMediaDirPath` <!-- unchecked --> | 取 media 目录绝对路径 |

### 统计 / 复习历史（评估学习计划用）

| action | 用途 | 返回要点 |
|---|---|---|
| ✅ `getNumCardsReviewedToday` | 今日复习总数 | 整数 |
| ✅ `getCollectionStatsHTML` | 完整统计页 HTML（含图表） | HTML 字符串 |
| ✅ `getNumCardsReviewedByDay` | **按天列复习数（看趋势）** | `[[日期, 数量], ...]` 全库所有有记录的天 |
| ✅ `cardReviews` | **取某 deck 在某时间点后的复习记录（评估核心）** | revlog 记录数组 |
| 🟡 `getReviewsOfCards` <!-- unchecked --> | **取卡片完整复习历史** | — |
| 🟡 `getLatestReviewID` <!-- unchecked --> | 最新复习时间戳 | — |
| 🟡 `insertReviews` <!-- unchecked --> | 插入复习记录（**慎用，影响数据**） | — |

### GUI（驱动 Anki 界面）

| action | 用途 |
|---|---|
| 🟡 `guiBrowse` <!-- unchecked --> | 打开浏览器搜卡 |
| 🟡 `guiSelectCard` / `guiSelectNote` / `guiSelectedNotes` <!-- unchecked --> | 浏览器选卡 |
| 🟡 `guiAddCards` / `guiEditNote` <!-- unchecked --> | 打开加卡/编辑对话框 |
| 🟡 `guiCurrentCard` <!-- unchecked --> | 当前复习卡信息 |
| 🟡 `guiShowQuestion` / `guiShowAnswer` <!-- unchecked --> | 显示问题/答案面 |
| 🟡 `guiAnswerCard` <!-- unchecked --> | 答当前卡 |
| 🟡 `guiStartCardTimer` <!-- unchecked --> | 重置计时 |
| 🟡 `guiUndo` <!-- unchecked --> | 撤销 |
| 🟡 `guiDeckOverview` / `guiDeckBrowser` / `guiDeckReview` <!-- unchecked --> | 牌组界面 |
| 🟡 `guiImportFile` <!-- unchecked --> | 打开导入对话框 |
| 🟡 `guiCheckDatabase` <!-- unchecked --> | 检查数据库 |
| 🟡 `guiExitAnki` <!-- unchecked --> | 关闭 Anki |
| 🟡 `guiPlayAudio` <!-- unchecked --> | 播放音频 |
| 🟡 `guiReviewActive` <!-- unchecked --> | 是否在复习中 |

### 杂项 / 系统级

| action | 用途 |
|---|---|
| ✅ `version` | API 版本（自检用） |
| 🟡 `multi` <!-- unchecked --> | **一次请求跑多个 action（减少往返，提稳定性）** |
| 🟡 `apiReflect` <!-- unchecked --> | 让 AnkiConnect 自报所有 API（元查询/调试） |
| 🟡 `requestPermission` <!-- unchecked --> | 请求 API 权限 |
| 🟡 `sync` <!-- unchecked --> | 同步 AnkiWeb（**fire-and-forget，可能静默排队**） |
| 🟡 `getProfiles` / `getActiveProfile` / `loadProfile` <!-- unchecked --> | 用户档案 |
| 🟡 `exportPackage` / `importPackage` <!-- unchecked --> | 导出/导入 .apkg |
| 🟡 `reloadCollection` <!-- unchecked --> | 重载数据库 |

### ❌ 源码里不存在（实测确认，不要调）

以下 action 源码里**没有定义**，是常见的 LLM 幻觉目标：

```
getConfig, getGlobalConfig, getCollectionConfig, getConf, getConfigs, getMeta,
getPreferences, getReviewCount, getReviews, getMisc, getDeckNamesById,
getDeckConfigs（全局版）, saveConfig, enableFsrs, setScheduler
```

> 含义：**全局配置（包括 FSRS 总开关、scheduler 切换）curl 够不着**。详见「FSRS 边界」。

---

## 模板

### 通用调用形式

```bash
curl -s -X POST http://localhost:8765 \
  -H "Content-Type: application/json" \
  -d '{"action":"<ACTION>","version":6,"params":{...}}'
```

返回结构恒为 `{"result": <数据或null>, "error": <字符串或null>}`。**调用后必须检查 error 字段**——非 null 就是失败，别看 result。

### 模板 1：建牌组（addNote 前必做）

```bash
curl -s -X POST http://localhost:8765 -d '{
  "action":"createDeck",
  "version":6,
  "params":{"deck":"Biology::Photosynthesis"}
}'
```

> AnkiConnect **不会自动建牌组**。addNote 时如果牌组不存在会直接报错。流程：createDeck → addNote。

### 模板 2：批量建卡

```bash
curl -s -X POST http://localhost:8765 -d '{
  "action":"addNotes",
  "version":6,
  "params":{"notes":[
    {
      "deckName":"Biology::Photosynthesis",
      "modelName":"Basic",
      "fields":{"Front":"光合作用的反应物？","Back":"CO₂ 和 H₂O"},
      "tags":["source::chat","topic::photosynthesis"]
    }
  ]}
}'
```

### 模板 3：查重（findNotes + notesInfo 两步）

```bash
# 第1步：搜
curl -s -X POST http://localhost:8765 -d '{
  "action":"findNotes",
  "version":6,
  "params":{"query":"deck:Biology::Photosynthesis 光合作用 反应物"}
}'
# → [1234, 5678]

# 第2步：取内容比对
curl -s -X POST http://localhost:8765 -d '{
  "action":"notesInfo",
  "version":6,
  "params":{"notes":[1234, 5678]}
}'
```

### 模板 4：读牌组配置（含 FSRS）

```bash
curl -s -X POST http://localhost:8765 -d '{
  "action":"getDeckConfig",
  "version":6,
  "params":{"deck":"目标牌组名"}
}'
```

返回里包含 FSRS 相关字段：`fsrsWeights` / `fsrsParams5` / `fsrsParams6` / `desiredRetention` / `sm2Retention`。

> 注意：返回 `false` 或 `null` 通常意味着这个牌组**没有独立配置组**（继承父级）。用有独立配置的牌组名查。

### 模板 5：改学习计划参数（desiredRetention / fsrsWeights）

**关键：必须先 get 全量，改完再 save，不能只传部分字段。**

```bash
# 步骤见下方「三坑-坑3」的完整往返代码
# 核心是：getDeckConfig 拿全量 → 改 desiredRetention/fsrsWeights → saveDeckConfig 写回 → getDeckConfig 验证
```

### 模板 6：拉学习计划评估数据

```bash
# 各牌组今日进度
curl -s -X POST http://localhost:8765 -d '{
  "action":"getDeckStats",
  "version":6,
  "params":{"decks":["Skills","统计学","逻辑学"]}
}'
# 返回每牌组的 new_count/learn_count/review_count

# 某张卡的 FSRS 预测（未来间隔）
curl -s -X POST http://localhost:8765 -d '{
  "action":"getIntervals",
  "version":6,
  "params":{"cards":[1784466326973],"complete":true}
}'
# → [[-1200, -1800, 5, 6, 9]]  （负数=分钟，正数=天）
```

### 模板 7：复习历史与趋势评估

```bash
# 全库每天的复习量（看学习连贯性/趋势）——注意：无参数，返回所有有记录的天
curl -s -X POST http://localhost:8765 -d '{
  "action":"getNumCardsReviewedByDay","version":6,"params":{}
}'
# 返回：[["2026-08-10", 14], ["2026-08-08", 3], ...]  按日期降序

# 取某 deck 在某时间点之后的复习记录（算保留率/失败率的核心数据）
curl -s -X POST http://localhost:8765 -d '{
  "action":"cardReviews","version":6,
  "params":{"deck":"Skills","startID":<毫秒级unix时间戳>}
}'
# 注意：startID 是毫秒级（不是秒）。若返回空，可能该 deck 还没卡被复习过（用 findCards "reviewed:N" 验证）

# 取一批卡片的完整复习历史（比 cardReviews 更聚焦）
curl -s -X POST http://localhost:8765 -d '{
  "action":"getReviewsOfCards","version":6,"params":{"cards":[1784466326973]}
}'
```

评估思路：拿到复习记录后，用 `reviewType`（1=学习/2=复习/3=relearn）+ `ease`（答对=1/2/3/4）算保留率。某个 deck 的失败率持续偏高 → 提示用户"这批卡可能质量低/太难，考虑拆细或降量"。

### 模板 8：调控学习计划 <!-- unchecked -->

> 直接改计划的 action，全部 🟡，调用前验证 schema。改完**必须读回验证**（同坑 3 的逻辑）。

```bash
# 改某张卡的到期日（提前/延后）
curl -s -X POST http://localhost:8765 -d '{
  "action":"setDueDate","version":6,
  "params":{"cards":[1784466326973],"days":"3"}
}'

# 挂起一批卡（暂停某 deck 的复习，比如考前集中）
curl -s -X POST http://localhost:8765 -d '{
  "action":"suspend","version":6,"params":{"cards":[1784466326973]}
}'

# 重置为新卡（彻底重学）
curl -s -X POST http://localhost:8765 -d '{
  "action":"forgetCards","version":6,"params":{"cards":[1784466326973]}
}'
```

### 模板 9：multi 批量调用（减少往返）<!-- unchecked -->

`multi` 把多个 action 打包成一次 HTTP 请求——**减少 curl 往返次数，是提升稳定性的关键手段**。读多 deck 的 config + stats 这种场景特别有用。

```bash
curl -s -X POST http://localhost:8765 -d '{
  "action":"multi","version":6,
  "params":{"actions":[
    {"action":"getDeckStats","version":6,"params":{"decks":["Skills","统计学"]}},
    {"action":"getDeckConfig","version":6,"params":{"deck":"Skills"}},
    {"action":"getNumCardsReviewedToday","version":6}
  ]}
}'
# 返回数组，顺序与请求一一对应
```

---

## 四坑

这四个坑都来自实测，每个都有明确的防御方法。

### 坑 1：LLM 幻觉 action 名

LLM 会编造看似合理但**不存在**的 action（比如 `getConfig`、`getReviewCount`、`enableFsrs`）。AnkiConnect 会返回 `unsupported action`，但如果你不检查 error 字段就会误以为成功。

**防御**：只调用「白名单」表里的 action。不确定某个 action 是否存在时，**先查白名单，不在表里就别调**。白名单是实测验证过的，可以信任。

### 坑 2：中文牌组名 / 特殊字符

牌组名含中文、空格（如 `git 杂项`）时，直接写进 JSON 通常能工作，但要注意：
- JSON 里的中文要确保 UTF-8 编码正确（curl `-d` 配合正确编码的 shell）
- 牌组名含 `::` 是正常的（Anki 层级分隔符），不是 bug
- **有些牌组返回 null/false 不是 bug**——它们没有独立配置组（继承父级），查它的父牌组

**防御**：先用 `deckNames` 拿到真实牌组名再操作，别靠猜。

### 坑 3：saveDeckConfig 部分写会静默失败（最隐蔽的坑）

`saveDeckConfig` 如果只传部分字段（比如只传 `{id, name, desiredRetention}`），会**返回 `false` 但不报错**——配置没改成功，你以为成功了。这是 curl 路径最危险的静默失败。

**防御：必须传完整 config 对象。** 标准往返流程：

```bash
# 1. 读全量
cfg=$(curl -s -X POST http://localhost:8765 -d '{
  "action":"getDeckConfig","version":6,"params":{"deck":"目标牌组"}
}')

# 2. 改字段（用脚本改，保留其他字段不动）
# 3. 写回（传改后的完整对象）
curl -s -X POST http://localhost:8765 -d "{
  \"action\":\"saveDeckConfig\",\"version\":6,
  \"params\":{\"config\":$改后的完整cfg}
}"

# 4. 读回验证（必须做！不验证等于没改）
curl -s -X POST http://localhost:8765 -d '{
  "action":"getDeckConfig","version":6,"params":{"deck":"目标牌组"}
}'
# 确认 desiredRetention/fsrsWeights 确实变成新值
```

**写完必读回验证**——这一步不能省，是防静默失败的唯一手段。

### 坑 4：deleteDecks 必须带 cardsToo:true

Anki 2.1.28+ 起，`deleteDecks` 如果传 `cardsToo:false` 会报错：`"it's not possible to delete decks without deleting cards as well"`。即**删牌组必须连带删里面的卡**。

**防御**：删牌组永远带 `cardsToo:true`。如果只想删空牌组（卡已先用 `deleteNotes` 删掉），也照样传 `true`——此时牌组里已经没卡，不会误删。

```bash
curl -s -X POST http://localhost:8765 -d '{
  "action":"deleteDecks","version":6,
  "params":{"decks":["__test__"],"cardsToo":true}
}'
```

> 想保留卡、只移走它们？用 `changeDeck` 先把卡移到别的牌组，再 `deleteDecks`。

---

## FSRS 边界

这是 curl 能力的天花板，必须记清：

### ✅ curl 能做的（已实测）

- 读 `fsrsWeights` / `fsrsParams5` / `fsrsParams6` / `desiredRetention`
- 改 `desiredRetention`（目标保留率）
- 改 `fsrsWeights`（注入 FSRS 权重数组，如 17 维）

### ❌ curl 够不着的

- **全局 FSRS 总开关**（首次激活 scheduler）：所有全局 config action（`getConfig`/`getGlobalConfig`/`getConf` 等）都不存在。

### 含义

**FSRS 的"首次激活"必须用户在 Anki GUI 手动操作一次**（牌组 → 选项 → 勾选 FSRS）。**一旦开启后**，调权重、调 desired retention、注入优化参数——这些日常调优 curl 全能做。

如果用户要开 FSRS，给一句指引：
> 请在 Anki 里：打开牌组 → 点"选项"（齿轮）→ 勾选 "FSRS"。这是一次性操作，之后调参我可以帮你自动做。

---

## 学习计划数据

评估学习计划需要的数据，curl 全能拿到：

| 评估维度 | 数据来源 | action | 状态 |
|---|---|---|---|
| 今日各牌组进度 | new/learn/review 计数 | `getDeckStats` | ✅ |
| 今日总复习量 | 整数 | `getNumCardsReviewedToday` | ✅ |
| 单卡掌握程度 | interval/reps/lapses/factor | `cardsInfo` | ✅ |
| 单卡未来间隔预测 | FSRS 预测的下一档间隔 | `getIntervals` | ✅ |
| 难度分布 | 全卡 ease factor | `getEaseFactors`（需配合 findCards 取 cardId） | ✅ |
| 完整统计页 | 图表 HTML | `getCollectionStatsHTML` | ✅ |
| 当前保留率设置 | desiredRetention | `getDeckConfig` | ✅ |
| 近 N 天复习量趋势 | 每日复习数数组（全库所有有记录的天） | `getNumCardsReviewedByDay` | ✅ |
| 某 deck 的完整复习记录 | 单次复习记录（含答对率） | `cardReviews` | ✅ |
| 某卡的完整复习历史 | 该卡所有历史 | `getReviewsOfCards` | 🟡 <!-- unchecked --> |

调控学习计划（不只读，直接改）：

| 调控动作 | action | 状态 |
|---|---|---|
| 改卡片到期日 | `setDueDate` | 🟡 <!-- unchecked --> |
| 挂起/恢复卡片 | `suspend` / `unsuspend` | 🟡 <!-- unchecked --> |
| 重置为新卡（重学） | `forgetCards` | 🟡 <!-- unchecked --> |
| 改目标保留率/FSRS权重 | `saveDeckConfig` | ✅ |
| 批量操作减少往返 | `multi` | 🟡 <!-- unchecked --> |

> 用 `getCollectionStatsHTML` 拿到的是带 base64 图的 HTML，需要解析才能提取数字。日常评估优先用前几个结构化 action，HTML 留给"要看图时"。

### 验证标记说明

文中所有 `🟡` + `<!-- unchecked -->` 标记的 action，是从 AnkiConnect 源码确认存在但**尚未在本机实测**的。验证方法：

1. Anki 开着时，按模板格式调一次该 action
2. 确认返回 `error:null` 且 `result` 符合预期
3. **删掉该行的 `<!-- unchecked -->`**，并把 `🟡` 改成 `✅`
4. 顺手补一下"返回要点"列的实际返回值

批量清理未验证标记：`grep -l "unchecked" references/anki-control.md` 找到后逐个验。

---

## 为什么用 curl 而不是 MCP

本 Skill 不依赖外部 MCP server，原因：

1. **AnkiConnect 本身已是本地 HTTP server**——再包一层 MCP 是"用 server 包 server"，多一个进程、多一个故障点。
2. **调用简单无状态可逆**——curl 直接调，不需要 MCP 的 schema 校验兜底。
3. **MCP 救不了核心风险**——Anki 一升级 AnkiConnect 可能挂，这是 #1 风险，MCP wrapper 同样继承这个风险。
4. **灵活性**——评估学习计划是动态判断，curl + LLM 推理比 MCP 的固定工具更灵活。

代价是丢了 schema 校验，但用「白名单」+「三坑防御」补回来了。详见 SKILL.md 的设计说明。
