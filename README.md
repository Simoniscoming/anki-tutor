# anki-cards

一个 Claude Code Skill：把文本 / 笔记 / 代码 / 公式 / 图片拆成高质量的原子 Anki 闪卡，预览确认后写入 Anki。

核心信念：**Anki 是记一辈子的库，AI 任何一处幻觉都会把错误信息刻进大脑。** 所以宁可慢一步（先预览、先查重、先等确认），也不批量直写。

## 依赖

这个 Skill 本身只是 markdown，但要真正写卡，需要以下运行环境：

1. **Anki 桌面端**（开着，因为要写库）
2. **AnkiConnect 插件**（在 Anki 里安装，默认监听 `http://localhost:8765`）

> **不需要 MCP。** 本 Skill 通过 curl 直接调用 AnkiConnect 的 HTTP 接口，不依赖任何外部 MCP server。详见 `references/anki-control.md`。

## 安装 Skill

### 方式 A：项目级（仅当前项目可用）

把本仓库 clone 到项目的 `.claude/skills/anki-cards/`：

```bash
# 在项目根目录执行（.claude/skills/ 需已存在、anki-cards 子目录需不存在）
git clone https://github.com/Simoniscoming/HiTutor.git .claude/skills/anki-cards
```

### 方式 B：全局（所有项目可用）

```bash
git clone https://github.com/Simoniscoming/HiTutor.git ~/.claude/skills/anki-cards
```

Windows 上 `~` 即 `C:\Users\<你的用户名>`。

> 优先级：同名 Skill 下，项目级会覆盖全局。可据此做"全局稳定版 + 项目级实验版"的双轨管理。

## 用法

在 Claude Code 里贴一段要记的内容，或说"做成 anki 卡片""帮我背这个""这段老记不住"等。Skill 会拆卡 → 预览 → 等你确认 → 写入 Anki。

## 更新

Skill 是磁盘上的静态文件，Claude Code 不会自动更新，需手动 pull：

```bash
git -C <Skill 安装路径> pull
```

改动在**下次** Claude 会话生效。
