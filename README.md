# anki-tutor

一个 Skill：把内容变成高质量 Anki 闪卡，也当你的间隔重复"教练"——造卡 + 诊断优化，一个搞定。

## 为什么用它

- **说句话就成卡。** 贴一段文本、代码、公式，甚至甩张截图，它自动拆成一张张原子闪卡，你点头就写进 Anki——从此告别逐张手敲。
- **造卡不出错，三道闸把关。** 写入前先预览、先查重，拆卡遵循 SuperMemo 创始人的 Wozniak 法则。AI 再会幻觉，错卡也进不了你的脑子。
- **它还是你的复习教练。** 读你的真实保留率，告诉你学得到底怎么样；更预测"每天加这么多新卡，几个月后复习会不会爆"——这种事 Anki 自己不会提醒你。
- **诊断结果一键变看板。** 每次诊断自动生成一份自包含 HTML 看板（保留率对比、复习量趋势、leech 明细、建议动作），本地直接在浏览器打开；纯聊天环境自动降级为文字版摘要，不挑平台、可离线查看。
- **FSRS 不用自己调，和 AI 聊目标就行。** 那些枯燥的调优参数全交给它——你说"考研还剩 100 天"，它就配好速通配方、反推每天该加多少新卡；还记着你的 deadline，不会把你刻意的"速通"劝退成"长期最优"。
- **零依赖、多平台、改库永远你点头。** 不用装 MCP，Claude Code / ZCode / 任何认 SKILL.md 的 agent 都能跑；诊断全程只读，任何写入都要你确认——你的库，你做主。

## 怎么用

在你的 agent 里直接说人话，三种意图它都认：

```
"把这段光合作用做成 anki 卡"       # 制卡
"看看我最近的 retention 怎么样"     # 诊断
"考研还剩 100 天，FSRS 怎么配"     # 配置
```

## 平台兼容

本 Skill 是一份纯 markdown（遵循 `SKILL.md` frontmatter 约定），不绑定特定 agent。只要你的 agent 支持 SKILL.md 规范就能用，已在以下平台验证：

- **Claude Code**
- **ZCode**
- 其它兼容 SKILL.md 约定的 agent

## 依赖

这个 Skill 本身只是 markdown，但要真正写卡，需要以下运行环境：

1. **Anki 桌面端**（开着，因为要写库）
2. **AnkiConnect 插件**（在 Anki 里安装，默认监听 `http://localhost:8765`）

> **可选**：Python 3.7+。启用 `scripts/anki_probe.py` 后，查重、诊断采集、空牌组扫描这些只读操作由脚本一次跑完（防编码坑、防误建空牌组）。没装 Python 则自动降级为 curl 手工流程，功能不缺。

> **不需要 MCP。** 本 Skill 通过 curl 直接调用 AnkiConnect 的 HTTP 接口，不依赖任何外部 MCP server。详见 `references/anki-control.md`。

## 安装 Skill

把仓库 clone 到你 agent 约定的 skills 目录。**clone 时显式指定目标目录名为 `anki-tutor`**（与 skill 名一致，避免混乱）：

### Claude Code

```bash
# 项目级（仅当前项目可用）
git clone https://github.com/Simoniscoming/anki-tutor.git .claude/skills/anki-tutor

# 全局（所有项目可用）
git clone https://github.com/Simoniscoming/anki-tutor.git ~/.claude/skills/anki-tutor
```

### ZCode

```bash
# 用户级（所有项目可用）
git clone https://github.com/Simoniscoming/anki-tutor.git ~/.agents/skills/anki-tutor

# 项目级（仅当前项目可用）
git clone https://github.com/Simoniscoming/anki-tutor.git .agents/skills/anki-tutor
```

> Windows 上 `~` 即 `C:\Users\<你的用户名>`。
> 同名 Skill 下，项目级会覆盖用户级。可据此做"用户级稳定版 + 项目级实验版"双轨。

### 其它兼容 SKILL.md 的 agent

放进你 agent 约定的 skills 目录即可（具体路径查你 agent 的文档）。只要它认 `SKILL.md` 的 frontmatter，就能识别本 Skill。

## 更新

Skill 是磁盘上的静态文件，agent 不会自动更新，需手动 pull：

```bash
git -C <Skill 安装路径> pull
```

改动在**下次**会话生效。

## License

MIT — 见 [LICENSE](./LICENSE)。可自由使用、修改、分发（含商用），保留版权声明即可。
