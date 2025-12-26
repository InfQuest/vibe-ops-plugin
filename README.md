# Vibe Ops Plugin

A collection of Claude Code skills designed for operations teams - macOS app installation, video processing, and more.

## Installation

```bash
# Add marketplace
/plugin marketplace add InfQuest/vibe-ops-plugin

# Install plugin
/plugin install vibe-ops@vibe-ops
```

## Skills

| Skill | Description | Triggers |
|-------|-------------|----------|
| **install-app** | macOS app installation with Homebrew (auto-installs Homebrew if needed, configures USTC mirror) | 安装, install, 帮我装 |
| **video-concat** | Merge multiple video files into one | 合并视频, 拼接视频, merge videos |
| **video-trim** | Trim video segments with compression options | 剪辑视频, 裁剪视频, trim video |

## Usage Examples

```
帮我安装 Chrome
把这几个视频合并成一个
裁剪视频从 1:30 到 3:45
```

## Development

### Local Testing

```bash
claude --plugin-dir .
```

### Project Structure

```
vibe-ops-plugin/
├── .claude-plugin/
│   ├── plugin.json        # Plugin manifest
│   └── marketplace.json   # Marketplace config
├── skills/
│   ├── install-app/       # macOS app installation
│   ├── video-concat/      # Video merging
│   └── video-trim/        # Video trimming
├── CLAUDE.md
└── README.md
```

## License

MIT
