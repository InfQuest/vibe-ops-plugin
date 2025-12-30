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
| **audio-extract** | Extract audio from video files | 提取音频, 抽取音频, extract audio |
| **audio-transcribe** | Speech to text using Whisper with word-level timestamps | 语音转文字, transcribe, 字幕生成 |
| **image-gen** | AI image generation via OpenRouter API (Gemini, Seedream) | 生成图片, 画图, generate image |
| **install-app** | macOS app installation with Homebrew (auto-installs Homebrew if needed, configures USTC mirror) | 安装, install, 帮我装 |
| **video-concat** | Merge multiple video files into one | 合并视频, 拼接视频, merge videos |
| **video-trim** | Trim video segments with compression options | 剪辑视频, 裁剪视频, trim video |

## Usage Examples

```
帮我把视频的音频提取出来
帮我把这个音频转成文字
帮我生成一张图片，一只在星空下的猫
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
│   ├── audio-extract/     # Audio extraction from video
│   ├── audio-transcribe/  # Speech to text (Whisper)
│   ├── image-gen/         # AI image generation
│   ├── install-app/       # macOS app installation
│   ├── video-concat/      # Video merging
│   └── video-trim/        # Video trimming
├── CLAUDE.md
└── README.md
```

## License

MIT
