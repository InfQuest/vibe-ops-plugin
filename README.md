# Vibe Ops Plugin

A Claude Code plugin for vibe-driven operations and developer workflow automation.

## Installation

```bash
# Install from local directory
claude /plugin install ./vibe-ops-plugin

# Or test during development
claude --plugin-dir ./vibe-ops-plugin
```

## Commands

| Command | Description |
|---------|-------------|
| `/vibe-ops:hello` | Greet and introduce plugin capabilities |
| `/vibe-ops:status` | Check project status and provide summary |

## Skills

- **code-review**: Automated code review that analyzes changes and provides feedback

## Development

### Prerequisites
- Claude Code CLI installed
- Git for version control

### Local Testing
```bash
cd vibe-ops-plugin
claude --plugin-dir .
```

### Project Structure
```
├── .claude-plugin/plugin.json  # Plugin manifest
├── commands/                   # Slash commands
├── skills/                     # Agent skills
├── hooks/                      # Event handlers
└── CLAUDE.md                   # Project docs for Claude
```

## License

MIT
