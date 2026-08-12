# anki-tutor

一个 Skill：把文本 / 笔记 / 代码 / 公式 / 图片拆成高质量的原子 Anki 闪卡，预览确认后写入 Anki。

核心信念：**Anki 是记一辈子的库，AI 任何一处幻觉都会把错误信息刻进大脑。** 所以宁可慢一步（先预览、先查重、先等确认），也不批量直写。

## 平台兼容

本 Skill 是一份纯 markdown（遵循 `SKILL.md` frontmatter 约定），不绑定特定 agent。只要你的 agent 支持 SKILL.md 规范就能用，已在以下平台验证：

- **Claude Code**
- **ZCode**
- 其它兼容 SKILL.md 约定的 agent

## 依赖

这个 Skill 本身只是 markdown，但要真正写卡，需要以下运行环境：

1. **Anki 桌面端**（开着，因为要写库）
2. **AnkiConnect 插件**（在 Anki 里安装，默认监听 `http://localhost:8765`）

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

## 用法

在你的 agent 里贴一段要记的内容，或说"做成 anki 卡片""帮我背这个""这段老记不住"等。Skill 会拆卡 → 预览 → 等你确认 → 写入 Anki。

## 更新

Skill 是磁盘上的静态文件，agent 不会自动更新，需手动 pull：

```bash
git -C <Skill 安装路径> pull
```

改动在**下次**会话生效。

## License

MIT — 见 [LICENSE](./LICENSE)。可自由使用、修改、分发（含商用），保留版权声明即可。
