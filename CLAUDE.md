# Vibe Ops Plugin

面向非技术用户的 Claude Code 插件，提供常用操作的自动化技能。

## Project Structure

```
vibe-ops-plugin/
├── .claude-plugin/
│   └── plugin.json       # Plugin manifest (required)
├── skills/
│   ├── install-app/      # macOS 软件安装
│   │   └── SKILL.md
│   ├── video-concat/     # 视频合并
│   │   └── SKILL.md
│   └── video-trim/       # 视频裁剪
│       └── SKILL.md
├── CLAUDE.md             # This file
└── README.md             # Documentation
```

## Skills

| Skill | 功能 | 触发词 |
|-------|------|--------|
| install-app | macOS 软件安装（自动处理 Homebrew） | 安装、install、帮我装 |
| video-concat | 合并多个视频文件 | 合并视频、拼接视频、merge videos |
| video-trim | 裁剪视频片段 | 剪辑视频、裁剪视频、trim video |

## Adding Skills

1. 在 `skills/` 下创建子目录
2. 创建 `SKILL.md` 文件，包含：
   - YAML frontmatter（`name` 和 `description` 必需）
   - 详细的执行步骤

```yaml
---
name: skill-name
description: 功能描述。Use when user wants to 触发词1, 触发词2, trigger1, trigger2.
---
```

## Testing

```bash
claude --plugin-dir .
```

## Notes

- `plugin.json` 必须放在 `.claude-plugin/` 目录
- Skills 使用中英双语触发词，方便不同用户
- 面向非技术用户，交互使用简单友好的语言
