# scripts/ —— anki-tutor 的辅助脚本

## anki_probe.py（v1，只读探测）

用法、子命令、退出码、降级条件见 [`../references/anki-control.md`](../references/anki-control.md)「脚本优先」节。这里只记两条硬规则：

- **只读铁律**：脚本绝不调用写操作；带牌组名的 action 一律先与 `deckNames` 返回精确比对，比对不上报错退出（坑 6 防御）。将来若加写入脚本，另起文件、默认 dry-run，不混进本文件。
- **纯标准库**：不引 pip 依赖，Python 3.7+（低于此版本启动即报错退出，由 skill 降级 curl）。

## 评估协议（改脚本后必须重跑）

**测试资产放包外**（打包/上传 git 时天然消失）：`%APPDATA%\anki-coach\evals\`（Windows）或 `~/.local/share/anki-coach/evals/`。造数脚本、快照、结果记录都放那里，本目录只留方法论。

### 标准测试提示（对应 skill-creator 的 eval 循环，一次跑一个、和用户一起看结果）

1. 「查重：<牌组> 里有没有关于 <关键词> 的卡」→ 验 `dedup`（含中文 locale 模型）
2. 「看看我最近的 retention / 学得怎么样」→ 验 `collect`（数字与 retention-coaching.md 口径一致）
3. 「我的 Anki 怎么多了一堆空牌组」→ 验 `shells`

### 必跑断言

| 断言 | 方法 |
|---|---|
| 功能正确 | `collect` 指标对照手算预期值（evals 目录的 seed 脚本头部写死了预期值） |
| 决定论 | 各子命令 `--json` 连跑 3 次，剔除 `"ts"` 行后 md5 必须一致 |
| 坑 6 零副作用 | 全部测试前后各拍 `deckNames` 快照，diff 必须为空 |
| 故障注入 | `ANKI_URL` 指向空端口 → exit 1；传不存在的牌组名 → exit 2 且快照不变 |
| 上游形状 | `selftest` 全绿（Anki 升级后单独跑这个即可） |
| 预测诚实性 | 有限小库（总卡数 < 预测值）必须报"不适用/受总量封顶"，不得输出超过牌组总卡数的预测值；`forecast.basis` 必须是 actual（有实测引入时），config 上限只可作假设并明示 |

### 最近一次评估

2026-08-16 · Python 3.13 · AnkiConnect 6 · 中文 locale test profile：全部通过（含修复 2 个评估中发现的 bug：子牌组排除查询引号位置、notesInfo.cards 形状假设）。详见 evals 目录 `results-*.md`。

2026-08-16 追加 · **子 agent 干净上下文复跑**（3 个标准提示，无任何会话记忆，只靠 SKILL.md 路由）：路径全对、诊断全管线（含看板生成+history 落盘）独立走通、对 Anki 零写操作（快照 diff 为空）。发现 4 处文档/体验问题，均已修复：① `--json` 位置歧义（现子命令前后均可）② SKILL.md「纯查卡」与路由表的张力 ③ check 的 bridge 全局探测输出可读性 ④ 内置默认牌组溯源例外未记载。

2026-08-16 再追加 · **用户复核看板发现预测 bug**：forecast 误用牌组设置的 perDay 上限当"当前新卡/天"，导致 5 卡测试牌组被报"≈180 张/天"。已修（三层）：collect 改用 revlog 实测新卡引入速率（basis=actual/config-assumption）+ 物理封顶（≤牌组总卡数）；retention-coaching.md 方案 A 补语义；模板/dashboard.md 加预测卡红线（不适用态显示"—"）。评估断言表新增：**预测断言——有限小库必须报"不适用/封顶"，不得出现超总卡数的预测值**。
