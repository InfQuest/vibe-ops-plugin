---
name: image-understand
description: 使用 AI 理解和分析图片内容。Use when user wants to 理解图片, 分析图片, 图片识别, 看图说话, 图片问答, understand image, analyze image, describe image, image recognition, what is in this image, 这张图片是什么.
---

# Image Understanding

使用 Gemini 3 Pro Preview 通过 OpenRouter API 分析和理解图片内容。

## Prerequisites

1. `OPENROUTER_API_KEY` 环境变量
2. 需要安装 Node.js（如果未安装，请使用 `install-app` skill 来安装）

## Instructions

你是一个图片理解助手，帮助用户分析和理解图片内容。请按以下步骤操作：

### Step 1: 检查环境变量

首先验证 `OPENROUTER_API_KEY` 是否已设置：

```bash
[ -n "$OPENROUTER_API_KEY" ] && echo "API_KEY_SET" || echo "API_KEY_NOT_SET"
```

如果未设置，直接报错退出：「缺少 OPENROUTER_API_KEY 环境变量，无法分析图片。」

### Step 2: 检查 Node.js 安装

```bash
which node && node --version || echo "NOT_INSTALLED"
```

如果未安装，使用 `install-app` skill 来安装 Node.js。

### Step 3: 收集用户需求

**⚠️ 必须：使用 AskUserQuestion 工具收集用户的图片分析需求。不要跳过这一步。**

使用 AskUserQuestion 工具收集以下信息：

1. **图片路径**：让用户提供要分析的图片
   - 可以是本地文件路径
   - 支持的格式：PNG、JPG、JPEG、GIF、WebP

2. **分析类型**：用户想了解图片的什么内容
   - 选项：
     - "描述图片 - 详细描述图片中的内容 (Recommended)"
     - "识别文字 - 提取图片中的文字（OCR）"
     - "回答问题 - 我有具体问题想问"
     - "其他 - 自定义分析需求"

3. **具体问题**（如果用户选择"回答问题"或"其他"）：
   - 让用户输入想问的具体问题

4. **输出语言**：
   - 选项：
     - "中文 (Recommended)"
     - "English"

### Step 4: 执行脚本

使用 skill 目录下的 `image-understand.js` 脚本：

```bash
node /path/to/skills/image-understand/image-understand.js "IMAGE_PATH" "PROMPT" "LANGUAGE"
```

参数说明：
- IMAGE_PATH: 图片文件路径
- PROMPT: 用户的问题或分析需求
- LANGUAGE: 输出语言（chinese / english）

根据用户选择的分析类型，使用以下 prompt：

**描述图片**：
```
请详细描述这张图片的内容，包括：
1. 图片的主要元素和对象
2. 场景和背景
3. 颜色、构图和风格
4. 任何值得注意的细节
```

**识别文字（OCR）**：
```
请识别并提取这张图片中的所有文字内容。按照文字在图片中的位置，从上到下、从左到右进行整理输出。
```

**回答问题**：
使用用户输入的具体问题作为 prompt。

示例：
```bash
node skills/image-understand/image-understand.js "./photo.jpg" "请详细描述这张图片的内容" "chinese"
```

### Step 5: 展示结果

分析完成后：

1. 以清晰的格式展示 AI 的分析结果
2. 如果用户有后续问题，可以继续对话
3. 报告使用的 tokens（如果 API 返回）

### 常见问题处理

**API Key 无效**：
- 检查 key 是否正确复制
- 确认账户余额充足
- 访问 https://openrouter.ai/activity 查看使用记录

**图片加载失败**：
- 确认文件路径正确
- 检查文件格式是否支持
- 确认文件大小不超过 20MB

**分析结果不准确**：
- 尝试提供更具体的问题
- 确保图片清晰度足够
- 对于复杂图片，分多次提问

### 示例交互

用户：帮我看看这张图片里有什么 ./photo.jpg

助手：
1. 检查环境变量和 Node.js ✓
2. 使用 AskUserQuestion 确认分析类型
3. 执行脚本分析图片
4. 展示分析结果

### 交互风格

- 使用简单友好的语言
- 如果分析结果较长，分段展示
- 主动询问用户是否有后续问题
- 如果遇到错误，提供清晰的解决方案
