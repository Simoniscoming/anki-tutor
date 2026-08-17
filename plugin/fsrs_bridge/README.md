# fsrs_bridge —— FSRS 全自动优化的配套 Anki 插件

补上 AnkiConnect（端口 8765）没转发的两个 FSRS 能力：**优化参数（Optimize）** 和 **重排卡片（reschedule）**。让外部 CLI / anki-cards skill 能全程自动完成 FSRS 优化，不用用户去 GUI 点按钮。

与 AnkiConnect **共存**（不同端口），互不影响。

## 它解决什么问题

AnkiConnect 的 126 个 action 里没有 optimize / reschedule（已用 `apiReflect` 实测确认）。而这两个能力是"越用越好看"全自动闭环的唯一缺口。本插件直接调 Anki 内部公开 API（`col._backend.compute_fsrs_params` 和 `col.decks.update_deck_configs`），把它们暴露成 HTTP action。

## 安装

### 方式一：agent 自动装（推荐）

配合 anki-tutor Skill 使用时**通常不用手动装**：agent 检测到 8766 无响应，会自动把本目录复制进你的 addons21，你只需重启一次 Anki。自动装失败才走方式二。

### 方式二：手动装

**第 0 步（推荐，任何系统通用）**：Anki 主界面 工具 → 插件（Tools → Add-ons）→ 查看文件（View Files），文件管理器会直接打开你的 addons21 文件夹——改过 Anki 数据目录、Flatpak 版等任何情况都适用。

把整个 `fsrs_bridge` 文件夹复制进去。找不到 View Files 时按系统手动定位：

- **Windows**: `%APPDATA%\Anki2\addons21\`
- **macOS**: `~/Library/Application Support/Anki2/addons21/`（Library 默认隐藏：Finder 按 `Cmd+Shift+G` 粘贴路径前往）
- **Linux**: `~/.local/share/Anki2/addons21/`；Flatpak 版为 `~/.var/app/net.ankiweb.Anki/data/Anki2/addons21/`

然后：

1. 重启 Anki 桌面端。
2. 打开任意 profile 后，Anki 的控制台会打印 `[fsrs_bridge] listening on http://127.0.0.1:8766`。

> 文件夹名必须是 `fsrs_bridge`（下划线），不能含连字符——Python 包名限制，否则 `from .web import` 会失败。

## 要求

- Anki >= 24.0（FSRS 全套 API 稳定的版本下限）
- FSRS 已在该牌组启用（`fsrsStatus` 可查）

## API 契约

所有请求 POST 到 `http://localhost:8766`（端口由插件 `config.json` 的 `port` 决定，默认 8766），JSON-RPC 风格，与 AnkiConnect 调用方式一致：

```
{"action": "<action>", "version": 6, "params": {...}}
```

响应：`{"result": ..., "error": null}` 或 `{"result": null, "error": "..."}`

### fsrsStatus —— 查 FSRS 状态

```bash
curl -s http://localhost:8766 -d '{"action":"fsrsStatus","version":6,"params":{"deck":"Japanese::JLPT"}}'
```

```json
{"result": {"ankiVersion": "25.07", "v3scheduler": true,
            "deck": "Japanese::JLPT", "fsrsEnabled": true, "daysSinceLastOptimize": 42},
 "error": null}
```

不给 `deck` 则只返回全局调度器状态。`deck` 必须是已存在的牌组名（来自 deckNames）——查不到会报错（v2 起如此；旧版会静默创建空牌组，属 bug 已修）。

### fsrsOptimize —— 只算权重，不写库不重排

等价于 GUI 的 Optimize 按钮（预览新权重）。

```bash
curl -s http://localhost:8766 -d '{"action":"fsrsOptimize","version":6,"params":{"deck":"Japanese::JLPT","healthCheck":true}}'
```

```json
{"result": {"params": [0.41, 0.60, 2.4, ...], "fsrsItems": 12453,
            "healthCheckPassed": true},
 "error": null}
```

`fsrsItems` = 参与训练的复习数（< 1000 说明数据不够，优化意义有限；实测某牌组只有 3 条时返回空 `params`，属正常）。`params` 维度随 FSRS 版本（实测 Anki 26.05 = 21 维；FSRS-5=17、FSRS-6=19），代码 `list()` 自适应。也可传 `search` + `currentParams` 完全自定义。

### fsrsApply —— 一步优化全部 preset + 重排

等价于 GUI 的 "Save & Optimize" 并确认 reschedule。**会改写卡片调度**。

```bash
curl -s http://localhost:8766 -d '{"action":"fsrsApply","version":6,"params":{"deck":"Japanese::JLPT","fsrsReschedule":true}}'
```

```json
{"result": {"applied": true, "deck": "Japanese::JLPT",
            "fsrsReschedule": true, "configCount": 1},
 "error": null}
```

- `fsrsReschedule: false` = 只优化参数、不重排到期日（新权重在后续复习中逐步生效）
- `fsrsReschedule: true` = 立刻全库重排（GUI 会冻结几十秒，正常）

## 安全

- 只监听 `127.0.0.1`，不对外网暴露
- 不做鉴权（和 AnkiConnect 一样，默认信任本地）——若机器多用户，自行加防火墙规则

## 故障排查

| 现象 | 原因 / 处理 |
|---|---|
| 连接被拒 | 先读本目录 `bridge-status.json`（started/port/error）：`started:false` 看 error 定位（端口被占等）；文件不存在 = 插件没被 Anki 加载，确认文件夹在 addons21、Anki 已重启；加载链条细节看 `bridge-debug.log` |
| `unsupported action` | action 名拼错，或请求没走 `/` 根路径 |
| `需要 Anki >= 24.0` | 升级 Anki |
| 8766 端口被占 | 改本插件 `config.json` 的 `"port"`（工具 → 插件 → fsrs_bridge → 配置，或直接编辑 `addons21/fsrs_bridge/config.json`），重启 Anki |
| fsrsApply 期间 GUI 卡住 | 正常（主线程优化），等几十秒；原生 GUI 优化也一样 |

## 设计说明

- **线程模型**：照搬 AnkiConnect——非阻塞 socket + QTimer 25ms 轮询，所有 handler 跑 Qt 主线程，`mw.col` 操作绝对安全。代价是慢操作冻结 GUI，属已知取舍。
- **只调公开 API**：`compute_fsrs_params`、`update_deck_configs`、`get_deck_configs_for_update` 都是 Anki 版本化的稳定 RPC，不碰 `pub(crate)` 私有方法，Anki 升级风险低。
- **不依赖外部 Python 包**：直接复用 Anki 内置的 FSRS 优化算法（就是 GUI Optimize 按钮用的同一套），无需 fsrs-optimizer / PyTorch。
