# bootstrap：安装 / 升级 / 体检 / 自愈

> 触发时机：8765/8766 连不通、用户要求安装或修复、升级 skill 后顺带升级 fsrs_bridge。执行器是 `scripts/bootstrap.py`（纯标准库，Python 3.7+，幂等）。

## 怎么跑（固定顺序）

```bash
# 1. 先 dry-run：体检 + 打印将要执行的操作（零写入），给用户看一眼
python <skill目录>/scripts/bootstrap.py --dry-run    # macOS/Linux 用 python3

# 2. 用户确认后真跑
python <skill目录>/scripts/bootstrap.py

# 3. 需要等用户开/重启 Anki 时，可带着等待跑（探活轮询，就绪自动冒烟）
python <skill目录>/scripts/bootstrap.py --wait 60
```

**永远先 dry-run 再真跑**——既是对用户的确认制，也是防误写目标之外的保险。

## 退出码决定下一步

| 退出码 | 含义 | 动作 |
|---|---|---|
| 0 | 就绪（或 dry-run 完成） | 直接回到用户原任务（制卡/诊断） |
| 1 | 已装好，需用户动作 | 按脚本输出转述一句话：`needs_restart` →"重启一次 Anki"；`needs_open` →"打开 Anki 即可"，然后可用 `--wait` 等就绪 |
| 2 | 失败 | 看输出里的原因；走降级链（GUI 手动指引，同 fsrs-optimize.md「前置」的降级路径） |

## 它会做 / 不会做

**会**：
- 定位 Anki 数据目录（多候选时优先含 AnkiConnect 的那个——那是用户真实在用的）
- 端口探活（从目标 base 里插件的 config.json 派生端口，不猜全局状态）
- AnkiConnect 缺失时安装，来源顺序：`--ankiconnect-src`（显式指定）> skill 内置快照（`plugin/ankiconnect`，GPL v3 随附 LICENSE，未改上游代码）> ankiweb 下载兜底；安装后预写 meta.json（防每日更新提示）
- fsrs_bridge 安装/升级：与 skill 自带 `plugin/fsrs_bridge` 做 hash 比对，不一致才覆盖；覆盖时保留用户的 config.json 和状态自报文件
- 端口预写（`--ankiconnect-port` / `--bridge-port`，沙箱场景用）
- 冷/热装分流指引 + 就绪冒烟（deckNames / fsrsStatus，只读）

**不会**：
- 碰 profiles / collection（写操作只落在目标 addons21 内，脚本里有路径断言）
- 启动或关闭 Anki（关 Anki 的梯度方法见 anki-control.md `guiExitAnki` 条目）
- 在没装好时假装成功——退出码和 JSON 摘要说真话

## 排障

- 输出顶部的「环境状态」表：base / anki.exe / 两个组件的装没装、端口、在线状态
- fsrs_bridge 起没起来看状态自报：`addons21/fsrs_bridge/bridge-status.json`（详见 fsrs-optimize.md「状态自报」）
- AnkiConnect 装了但无响应：多半是 Anki 没开或端口被占（状态表会分开显示）
