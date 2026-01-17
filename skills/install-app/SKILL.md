---
name: install-app
description: 帮助用户在 macOS 上安装软件，自动处理 Homebrew 依赖。Use when user wants to install, 安装, 下载软件, 装一个, 帮我装, 我想安装, 如何安装 apps on macOS.
---

# Install App Skill

## 目标

帮助没有编程经验的用户在 macOS 上轻松安装软件。

## 执行步骤

### 1. 确认用户需求

首先友好地确认用户想要安装什么软件。如果用户没有明确说明，询问他们：
- 想安装什么软件？
- 软件的用途是什么？（帮助推荐正确的安装包）

### 2. 检查 Homebrew 是否已安装

运行以下命令检查：

```bash
which brew
```

### 3. 如果没有 Homebrew，先安装它

**重要**：在安装前，用简单易懂的语言向用户解释：
- Homebrew 是 macOS 上最流行的软件包管理器
- 它可以帮助你轻松安装和管理各种软件
- 安装过程可能需要几分钟，请耐心等待

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

安装脚本会先解释将要执行的操作，然后暂停等待用户确认后再继续。

### 4. 搜索软件包

帮用户搜索正确的软件包名称。

**注意**：所有 brew 命令都需要带上环境变量以使用国内镜像加速：

```bash
HOMEBREW_API_DOMAIN="https://mirrors.ustc.edu.cn/homebrew-bottles/api" \
HOMEBREW_BOTTLE_DOMAIN="https://mirrors.ustc.edu.cn/homebrew-bottles" \
brew search <软件名>
```

向用户解释搜索结果，帮助他们选择正确的包：
- **Formulae**：命令行工具
- **Casks**：图形界面应用程序（大多数用户需要的）

### 5. 安装软件

根据软件类型使用正确的命令（带镜像加速）：

**图形界面应用（Cask）**：
```bash
HOMEBREW_API_DOMAIN="https://mirrors.ustc.edu.cn/homebrew-bottles/api" \
HOMEBREW_BOTTLE_DOMAIN="https://mirrors.ustc.edu.cn/homebrew-bottles" \
brew install --cask <软件名>
```

**命令行工具（Formula）**：
```bash
HOMEBREW_API_DOMAIN="https://mirrors.ustc.edu.cn/homebrew-bottles/api" \
HOMEBREW_BOTTLE_DOMAIN="https://mirrors.ustc.edu.cn/homebrew-bottles" \
brew install <软件名>
```

### 6. 验证安装

安装完成后，帮助用户验证：
- 对于 Cask 应用：告诉用户可以在「应用程序」文件夹或 Launchpad 中找到
- 对于命令行工具：运行 `which <工具名>` 或 `<工具名> --version`

### 7. 常见问题处理

**如果安装失败**：
- 检查网络连接
- 尝试 `brew update` 更新 Homebrew
- 尝试 `brew doctor` 诊断问题

**如果需要密码**：
- 向用户解释这是 macOS 的安全机制
- 输入的是他们的 Mac 登录密码
- 输入时不会显示任何字符，这是正常的

## 常用软件快速参考

**注意**：执行时需要加上镜像环境变量前缀（见上方安装软件步骤）。

| 软件 | 包名 |
|------|------|
| Chrome | `google-chrome` |
| VS Code | `visual-studio-code` |
| WeChat | `wechat` |
| QQ | `qq` |
| Notion | `notion` |
| Slack | `slack` |
| Zoom | `zoom` |
| VLC | `vlc` |
| Rectangle | `rectangle` |
| 1Password | `1password` |

## 交互风格

- 使用简单友好的语言，避免技术术语
- 每一步都解释「为什么」要这样做
- 如果遇到错误，用通俗的语言解释并提供解决方案
- 安装完成后给予积极的反馈
