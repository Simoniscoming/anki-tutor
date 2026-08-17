# FSRS 自动优化与开关：用配套插件闭环

> 本文件是「全自动 FSRS 优化」的核心。**依赖配套插件 fsrs_bridge**（端口 8766），补上 AnkiConnect 够不着的 optimize / reschedule / FSRS 总开关。用户想优化 FSRS、或诊断发现该优化 / 没开 FSRS 时**读本文件**。

## 目录

- 何时读 ............................. 见下文「何时读」
- 前置：配套插件 ..................... 见下文「前置」
- 场景 A：开启 FSRS .................. 见下文「场景 A」
- 场景 B：优化 FSRS .................. 见下文「场景 B」
- optimize-log.json 协议 ............. 见下文「日志」
- 和现有 skill 的衔接 ................. 见下文「衔接」
- 红线 ............................... 见下文「红线」

---

## 何时读

- 用户主动："帮我优化 FSRS""更新下参数""我该不该重新优化"
- 诊断 / 制卡时**顺带发现信号**：攒够了新复习数据、距上次优化很久、或 `fsrsStatus` 查到没开 FSRS → 顺带提一句"可以重新优化了，要不要？"。**用户不理就不动**（呼应 SKILL.md：被动响应，不主动骚扰）

## 前置：配套插件

本文件的能力依赖 **fsrs_bridge 插件**（装在 `addons21/fsrs_bridge`，端口 **8766**），与 AnkiConnect（8765）共存。这是本 Skill 唯一依赖配套插件的环节——别的 reference 全是纯 curl 调 AnkiConnect。

- **插件在** → 全自动闭环，全程不让用户碰 Anki 界面
- **插件没装** → **先自动安装**（agent 自己动手，见下「自动安装 fsrs_bridge」），装好后请用户重启 Anki，再打 8766 验证
- **自动安装失败 / 重启后仍无响应** → **降级**：指引用户在 GUI 手动操作（优化点 Optimize 按钮、FSRS 开关在 deck options）。不强求装插件，但说一句"装了 fsrs_bridge 我可以全自动帮你做"

### 自动安装 fsrs_bridge（先动手，失败再降级）

8766 连不上 ≠ 一定没装（也可能只是没重启）。自动安装是幂等的——目标目录已存在就跳过不覆盖，所以放心直接走：

1. **定位 addons21**（按平台探测，存在即命中）：
   - Windows：`%APPDATA%\Anki2\addons21`
   - macOS：`~/Library/Application Support/Anki2/addons21`
   - Linux：`~/.local/share/Anki2/addons21`，另探 Flatpak 变体 `~/.var/app/net.ankiweb.Anki/data/Anki2/addons21`
   - 多个候选同时存在 → 优先选里面有 `2055492159`（AnkiConnect）的那个，那是用户真实在用的 Anki
2. **复制**：把本 Skill 自带的 `plugin/fsrs_bridge/` 整个文件夹复制为 `addons21/fsrs_bridge`（文件夹名保持下划线原样，不能改）。Anki 开着复制也没事，重启后才生效。端口被占时预写插件 `config.json` 的 `"port"`（默认 8766，不用改代码）。
3. **告知 + 验证**：说一句"插件已装好，请重启 Anki"；重启后打 `fsrsStatus` 确认 8766 活了；不通先看下面「状态自报」排障，回到全自动闭环。
4. **找不到 addons21 / 复制失败 / 重启后仍无响应** → 降级：GUI 手动指引 + 让用户照 `plugin/fsrs_bridge/README.md` 手动装（里面有 View Files 万能入口，任何系统都适用）。

### 状态自报（排障第一步）

Windows GUI 下插件的 print 完全不可见（Anki 的 logs/ 也不收），bridge 起没起来只能靠它自己落盘（插件 v2 起自带）：

- `addons21/fsrs_bridge/bridge-status.json` —— `{"started": true/false, "port": ..., "error": ...}`
- `addons21/fsrs_bridge/bridge-debug.log` —— 加载链条分段日志（import → hook 注册 → 读 config → listening）

8766 连不上时先读这两个文件再动手：`started:false` 带 error 就是根因（端口被占 / config 损坏）；**连文件都不存在 = 插件压根没被 Anki 加载**（查文件夹位置和名字）。

调用方式同 AnkiConnect（JSON-RPC，打 8766）：

```
curl -s http://localhost:8766 -d '{"action":"fsrsOptimize","version":6,"params":{...}}'
→ {"result":..., "error":null}
```

中文牌组名用 `--data-binary @文件`（同 anki-control.md 坑 2）。

四个 action（全部实测通过，详见 `plugin/fsrs_bridge/README.md`）：

| action | 作用 | 动数据吗 |
|---|---|---|
| `fsrsStatus` | 查 FSRS 状态、版本、距上次优化天数 | 否（只读）|
| `fsrsOptimize` | 算新权重（预览）| 否（只算不写）|
| `fsrsApply` | 应用优化（写回权重 + 可选重排卡片）| **是** |
| `fsrsSetEnabled` | 开 / 关 FSRS 总开关 | **是**（影响全库）|

> 带 `deck` 参数的 action，牌组名**必须来自 `deckNames` 的返回**且已存在：插件 v2 起查不到直接报错；旧版会静默创建空牌组（anki-control.md 坑 6 同类 bug），遇到旧版行为先提醒升级插件。

### curl 速查

四个 action 的真实调用（中文牌组名用 `--data-binary @文件` 避免编码错，同 anki-control.md 坑 2）：

```bash
# 场景 A：查 FSRS 状态（只读）
curl -s http://localhost:8766 -d '{"action":"fsrsStatus","version":6,"params":{"deck":"AI工程化"}}'
# → {"result":{"ankiVersion":"26.05","v3scheduler":true,"fsrsEnabled":true,"daysSinceLastOptimize":7}, ...}

# 场景 A：开启 FSRS（写，需用户确认）
cat > /tmp/req.json <<'EOF'
{"action":"fsrsSetEnabled","version":6,"params":{"deck":"AI工程化","enabled":true,"fsrsReschedule":true}}
EOF
curl -s --max-time 120 http://localhost:8766 --data-binary @/tmp/req.json

# 场景 B：算权重（只读，预览）
cat > /tmp/req.json <<'EOF'
{"action":"fsrsOptimize","version":6,"params":{"deck":"AI工程化","healthCheck":true}}
EOF
curl -s --max-time 120 http://localhost:8766 --data-binary @/tmp/req.json
# → {"result":{"params":[...21 个权重...],"fsrsItems":306,"healthCheckPassed":null}, ...}

# 场景 B：应用优化（写，默认不重排，需用户确认）
cat > /tmp/req.json <<'EOF'
{"action":"fsrsApply","version":6,"params":{"deck":"AI工程化","fsrsReschedule":false}}
EOF
curl -s --max-time 120 http://localhost:8766 --data-binary @/tmp/req.json
```

返回恒为 `{"result":..., "error":null}`；`error` 非 null 即失败，别看 result。

---

## 场景 A：开启 FSRS

**触发**：`fsrsStatus` 查到 `fsrsEnabled=false`（FSRS 没开）。

```
1. fsrsStatus 确认（看 v3scheduler + fsrsEnabled）
2. 对话里主动提议：「你还没开 FSRS，这是最大的优化杠杆。要帮你开吗？
    开了会用 FSRS 重新估算你所有卡片的记忆状态（一次性，可能要等一会）。」
3. 用户同意 → fsrsSetEnabled {"deck":牌组, "enabled":true, "fsrsReschedule":true}
4. fsrsStatus 读回确认 fsrsEnabled=true
5. 写 optimize-log.json（fsrsEnabled=true + 时间）
```

**边缘情况**：`v3scheduler=false`（连 v3 调度器都没开）→ 插件没暴露 `set_v3_scheduler`。新版 Anki 默认就是 v3，遇到这种旧库提示用户在 GUI 升级一次 scheduler（一次性，之后 FSRS 开关就能自动管了）。

**为什么主动帮开**：FSRS 是最大杠杆，没开时其他诊断 / 配方都在次优解上打转。一次确认就能补上，符合"不让用户碰 GUI"的原则。

---

## 场景 B：优化 FSRS

**触发**：用户主动提，或顺带发现信号（距上次优化久 + 攒了新数据）。

```
1. fsrsStatus 看距上次优化几天（并读 optimize-log.json 交叉校验）
2. fsrsOptimize {"deck":牌组, "healthCheck":true} 算新权重
3. 看 fsrsItems（参与训练的复习数）：
     < 1000  → 停。提示「数据还不够（当前 N 条），优化出的参数不稳，建议再攒攒」。不应用。
     >= 1000 → 继续
   实测注（2026-08-17）：fsrsItems 的口径比窗口 revlog 数严——导入的旧记录可能一条都
   不计入（实测 40 条 revlog 报 fsrsItems=0）。以 fsrsOptimize 返回为准，勿与 revlog 数互推。
4. 汇报 + 等确认：「距上次优化 X 天，又攒了 Y 条新复习。新权重算好了（用了 N 条数据）。
                   要不要应用？默认不重排卡片（温和，新参数慢慢生效）；要立刻重排告诉我。」
5. 用户同意 → fsrsApply {"deck":牌组, "fsrsReschedule":false}   ← 默认不重排
6. fsrsStatus 读回确认
7. 写 optimize-log.json
```

**默认不重排的理由**：温和，不打乱当前复习节奏，新参数在后续复习里自然渗透。资深用户普遍偏好这个。用户要立刻全库重排，传 `fsrsReschedule=true`（Anki 会冻结几十秒，正常）。

**数据门槛 1000**：社区经验值。实测 3 条返回空、306 条能算但偏少、1000 是较稳的门槛。低于它优化出的参数不稳，不如再攒。

---

## 日志

### optimize-log.json 协议

Anki 读不到"上次优化时间 / FSRS 开关历史"（AnkiConnect 盲区），skill 自己存。和 `intent.json` **同目录、同思路**（Anki 不存的元信息，skill 自己造真相源）：

- Windows: `%APPDATA%\anki-coach\optimize-log.json`
- macOS / Linux: `~/.local/share/anki-coach/optimize-log.json`

```json
{
  "version": 1,
  "fsrsEnabled": true,
  "fsrsEnabledChangedAt": "2026-08-13T10:00:00Z",
  "decks": {
    "AI工程化": {
      "lastOptimizeAt": "2026-08-13T10:00:00Z",
      "fsrsItems": 12453,
      "weights": [0.85, 2.77, ...],
      "weightsLength": 21,
      "rescheduled": false,
      "healthCheckPassed": true
    }
  }
}
```

### 字段说明

| 字段 | 说明 |
|---|---|
| `fsrsEnabled` | FSRS 总开关当前状态（交叉校验 fsrsStatus）|
| `fsrsEnabledChangedAt` | 上次开/关 FSRS 的时间 |
| `decks[deck].lastOptimizeAt` | 该牌组上次优化的时间 → 诊断时算"距今天数" |
| `decks[deck].fsrsItems` | 上次优化用了多少条复习数据 → 对比当前判断"又攒了多少新的" |
| `decks[deck].weights` | 上次写回的权重 → 对比 Anki 当前权重，抓 GUI 手改漂移 |
| `weightsLength` | 权重维度（实测 Anki 26.05 = 21；随 FSRS 版本变）|
| `rescheduled` | 上次优化有没有重排卡片 |
| `healthCheckPassed` | 上次优化的健康检查结果 |

### 写时机（执行成功后自动写，不问用户）

- `fsrsSetEnabled` 后 → 更新 `fsrsEnabled` + `fsrsEnabledChangedAt`
- `fsrsApply` 后 → 更新 `decks[deck]` 的整条 lastOptimize 记录

**这就是"自动执行时顺便记录"**——不用问用户"优化好了吗"、不用用户回报，skill 在执行成功的同一步顺手采顺手记。下次诊断读它，判断"又该优化了吗"。

### 读时机（诊断 / 触发判断时）

- `decks[deck].lastOptimizeAt` → 算距今天数
- `decks[deck].fsrsItems` → 上次数据量，对比当前 `fsrsOptimize` 的 `fsrsItems` 判断攒了多少新的
- `decks[deck].weights` → 对比 Anki 当前权重，抓 GUI 手改（呼应 retention-coaching.md 第三步"交叉校验防漂移"）
- `fsrsEnabled` → 交叉校验 `fsrsStatus`

失败 / 缺失 / 损坏 → 降级为"无日志"流程（用 `fsrsStatus` 的 `daysSinceLastOptimize` 兜底），不报错中断。

---

## 衔接

### 诊断层第 0 步（retention-coaching.md）

从"间接猜 FSRS 开关"升级：

- 用 `fsrsStatus` **直接查** v3scheduler + fsrsEnabled（比从 deck config 看权重字段准）
- 查到 `fsrsEnabled=false` → 走本文件**场景 A** 帮开（不再只是"指引用户去 GUI 点"）
- 这块是 skill 让用户碰 GUI 的最后一块盲区，现在补上了

retention-coaching.md 的「第 0 步」要相应更新，指向本文件。

### recipes.md 红线例外

recipes.md「绝不手调 fsrsWeights」红线，现在有**一个合法例外**：走本文件的插件链路（`fsrsApply` 用的是 Anki 内置优化算法，等价于点 Optimize 按钮，**不是手调**）。recipes.md「应用」节要加这个例外说明，指向本文件。

### 和 intent.json 的关系

- `intent.json`：存"用户为什么这么配"（配方、目标、deadline）
- `optimize-log.json`：存"skill 什么时候优化/开关了 FSRS"（执行历史）
- 两者同目录、互补，都是"Anki 不存的元信息，skill 自己存"

---

## 红线

- `fsrsSetEnabled` / `fsrsApply` 执行前**必须用户确认**（影响全库）。和制卡写入、改配置同级。
- `fsrsStatus` / `fsrsOptimize` 只读，可自动跑不用问。
- **绝不手调 fsrsWeights**（那串数字）。更新权重只走 `fsrsApply`（Anki 内置算法）。
- 依赖配套插件。插件没装 → agent 先自动安装（见「前置」），失败才降级为 GUI 指引，不强求。
- 优化后**默认不重排**（温和）。用户明确要重排才传 `fsrsReschedule=true`。
- 数据 **< 1000 条不应用优化**（参数不稳），只提示"再攒攒"。
- 写日志紧跟执行成功之后，不脱节（同 intent-persistence.md 精神）。
