---
name: browser
description: Browser automation with persistent page state. Use when users ask to navigate websites, fill forms, take screenshots, extract web data, test web apps, or automate browser workflows. Trigger phrases include "go to [url]", "click on", "fill out the form", "take a screenshot", "scrape", "automate", "test the website", "log into", or any browser interaction request.
---

# Browser Automation

使用 Playwright 通过 CDP 连接到 Max 的浏览器服务器，进行浏览器自动化操作。

## Prerequisites

1. 需要安装 Python 3.12
2. 需要安装 uv（如果未安装，请使用 `install-app` skill 来安装）
3. Max 必须正在运行（提供浏览器服务器）
4. 环境变量 `MAX_SESSION_ID` 必须已设置（由 Max 自动设置）

## Usage

When the user wants to automate browser tasks: $ARGUMENTS

## Instructions

你是一个浏览器自动化助手，使用 Playwright 通过 Max 的浏览器服务器帮助用户完成各种浏览器操作。

### 核心概念

- **Session**: 当前 Claude 会话，自动通过 `MAX_SESSION_ID` 环境变量识别
- **Page**: 浏览器页面，通过名称（name）标识，便于后续引用
- **持久化**: 页面状态在操作之间保持，可以多次交互同一页面
- **AI Snapshot**: ARIA 可访问性树快照，用于智能元素发现

### Step 1: 检查环境

首先验证 uv 是否已安装：

```bash
which uv && uv --version || echo "NOT_INSTALLED"
```

如果未安装，使用 `install-app` skill 来安装 uv。

检查浏览器服务器是否运行：

```bash
curl -s http://localhost:9222/ | head -1 || echo "SERVER_NOT_RUNNING"
```

如果服务器未运行，告诉用户需要确保 Max 正在运行。

### Step 2: 检查已有页面（重要！）

**在创建新页面之前，必须先检查是否有可复用的页面：**

```bash
uv run skills/browser/client.py list
```

查看输出中是否有：
1. **URL 匹配**：已打开目标网站（如用户要去小红书，检查是否已有 xiaohongshu.com 的页面）
2. **可复用页面**：用户之前创建的相关页面

**复用规则：**
- 如果已有目标网站的页面 → 直接使用该页面，不要创建新页面
- 如果没有匹配的页面 → 创建新页面

**示例：**
```bash
# 1. 先列出已有页面
uv run skills/browser/client.py list
# 输出: main (https://www.xiaohongshu.com/explore)

# 2. 发现已有小红书页面，直接使用，不要 create
uv run skills/browser/client.py goto main "https://www.xiaohongshu.com/search?keyword=xxx"
```

### Step 3: 理解用户意图

根据用户的请求，确定需要执行的操作：

| 用户意图 | 操作 |
|---------|------|
| 打开网页 | `goto` 或 `create` + `goto` |
| 截图 | `screenshot` |
| 点击元素 | `click` 或 `select-ref click` |
| 填写表单 | `fill` 或 `select-ref fill` |
| 鼠标悬停 | `hover` |
| 键盘输入 | `keyboard` |
| 提取文本 | `text` |
| 执行 JS | `evaluate` |
| 查看页面结构 | `snapshot` |
| 等待加载 | `wait-load`, `wait-selector`, `wait-url` |
| 查看页面信息 | `info` |
| 列出打开的页面 | `list` |
| 关闭页面 | `close` |

### Step 4: 执行操作

使用 skill 目录下的 `client.py` 脚本：

```bash
uv run /path/to/skills/browser/client.py <command> [arguments]
```

## 命令详解

### 基础操作

#### 列出所有页面
```bash
uv run skills/browser/client.py list
```

#### 创建新页面
```bash
uv run skills/browser/client.py create <page_name> [url]
```
- `page_name`: 页面名称（1-64 字符，只允许字母、数字、`-`、`_`）
- `url`: 可选，初始 URL

#### 导航到 URL
```bash
uv run skills/browser/client.py goto <page_name> <url>
```
- 如果页面不存在，会自动创建

#### 截图
```bash
uv run skills/browser/client.py screenshot <page_name> [output_path]
```
- 默认输出到 `<page_name>.png`

#### 关闭页面
```bash
uv run skills/browser/client.py close <page_name>
```

#### 获取页面信息
```bash
uv run skills/browser/client.py info <page_name>
```

### 元素交互

#### 点击元素
```bash
uv run skills/browser/client.py click <page_name> <selector>
```

#### 填写输入框
```bash
uv run skills/browser/client.py fill <page_name> <selector> <text>
```

#### 鼠标悬停
```bash
uv run skills/browser/client.py hover <page_name> <selector>
```

#### 键盘输入
```bash
uv run skills/browser/client.py keyboard <page_name> <key>
```
- 常用按键：`Enter`, `Tab`, `Escape`, `Backspace`, `ArrowUp`, `ArrowDown`

#### 提取元素文本
```bash
uv run skills/browser/client.py text <page_name> <selector>
```

### AI Snapshot（智能元素发现）

#### 获取 AI Snapshot
```bash
uv run skills/browser/client.py snapshot <page_name>
```
返回 YAML 格式的 ARIA 可访问性树，包含元素 ref（如 `[ref=e1]`）。

**Snapshot 输出示例**：
```yaml
- navigation "Main":
  - link "Home" [ref=e1]
  - link "Products" [ref=e2]
  - link "About" [ref=e3]
- main:
  - heading "Welcome" [level=1] [ref=e4]
  - textbox "Search" [ref=e5]
  - button "Submit" [ref=e6]
```

#### 通过 Ref 操作元素
```bash
uv run skills/browser/client.py select-ref <page_name> <ref> <action> [value]
```
- `action`: `click`, `fill`, `hover`, `text`
- `value`: 仅 `fill` 操作需要

**使用流程**：
1. 先执行 `snapshot` 获取页面结构
2. 从 snapshot 中找到目标元素的 ref
3. 使用 `select-ref` 操作该元素

### JavaScript 执行

```bash
uv run skills/browser/client.py evaluate <page_name> <script>
```
- 返回 JSON 格式的执行结果

### 等待操作

#### 等待页面完全加载
```bash
uv run skills/browser/client.py wait-load <page_name> [--timeout ms]
```
- 使用 Performance API 检测网络空闲状态
- 默认超时 10000ms

#### 等待元素出现
```bash
uv run skills/browser/client.py wait-selector <page_name> <selector> [--timeout ms]
```
- 默认超时 30000ms

#### 等待 URL 变化
```bash
uv run skills/browser/client.py wait-url <page_name> <url_pattern> [--timeout ms]
```
- 支持字符串或正则表达式
- 默认超时 30000ms

## 使用示例

### 示例 1: 打开网页并截图

```bash
# 创建页面并导航
uv run skills/browser/client.py goto main "https://example.com"

# 等待加载完成
uv run skills/browser/client.py wait-load main

# 截图
uv run skills/browser/client.py screenshot main example.png
```

### 示例 2: 使用 AI Snapshot 进行表单填写

```bash
# 打开登录页
uv run skills/browser/client.py goto app "https://app.example.com/login"

# 获取页面结构
uv run skills/browser/client.py snapshot app
# 输出:
# - textbox "Username" [ref=e1]
# - textbox "Password" [ref=e2]
# - button "Sign In" [ref=e3]

# 使用 ref 填写表单
uv run skills/browser/client.py select-ref app e1 fill "user@example.com"
uv run skills/browser/client.py select-ref app e2 fill "password123"
uv run skills/browser/client.py select-ref app e3 click

# 等待登录成功
uv run skills/browser/client.py wait-url app "**/dashboard"
```

### 示例 3: 搜索操作

```bash
# 打开 Google
uv run skills/browser/client.py goto search "https://www.google.com"

# 填写搜索框
uv run skills/browser/client.py fill search 'input[name="q"]' "Claude AI"

# 按回车
uv run skills/browser/client.py keyboard search Enter

# 等待结果加载
uv run skills/browser/client.py wait-selector search "#search"

# 截图结果
uv run skills/browser/client.py screenshot search search_results.png
```

### 示例 4: 提取页面数据

```bash
# 打开页面
uv run skills/browser/client.py goto data "https://example.com/data"

# 等待加载
uv run skills/browser/client.py wait-load data

# 提取标题
uv run skills/browser/client.py text data "h1"

# 使用 JavaScript 提取更多数据
uv run skills/browser/client.py evaluate data "Array.from(document.querySelectorAll('.item')).map(e => e.textContent)"
```

### 示例 5: 复杂交互

```bash
# 打开页面
uv run skills/browser/client.py goto app "https://app.example.com"

# 悬停显示下拉菜单
uv run skills/browser/client.py hover app ".dropdown-trigger"

# 等待菜单出现
uv run skills/browser/client.py wait-selector app ".dropdown-menu"

# 点击菜单项
uv run skills/browser/client.py click app ".dropdown-menu .settings"
```

## 选择器说明

Playwright 支持多种选择器：

| 类型 | 示例 | 说明 |
|------|------|------|
| CSS | `#id`, `.class`, `div.class` | 标准 CSS 选择器 |
| Text | `text=登录`, `text="Sign in"` | 按文本内容匹配 |
| XPath | `//button[@type="submit"]` | XPath 表达式 |
| Role | `role=button[name="Submit"]` | ARIA 角色 |
| Placeholder | `[placeholder="Email"]` | 按属性匹配 |

**推荐**: 优先使用 AI Snapshot + ref 方式，更智能且不需要了解页面结构。

## 页面命名建议

- 使用简短、有意义的名称：`main`, `search`, `login`, `dashboard`
- 避免特殊字符，只用字母、数字、`-`、`_`
- 同一会话中页面名称唯一

## 错误处理

**服务器未运行**：
```
Error: Browser server is not running.
Please make sure Max is open.
```
→ 确保 Max 应用正在运行

**Session ID 缺失**：
```
Error: MAX_SESSION_ID environment variable is required.
```
→ 确保从 Max 内部运行

**页面不存在**：
```
Error: Page 'xxx' not found
```
→ 先使用 `create` 或 `goto` 创建页面

**元素未找到**：
```
Error: Timeout waiting for selector
```
→ 检查选择器是否正确，或使用 `snapshot` 查看页面结构

**Snapshot Ref 未找到**：
```
Error: No snapshot refs found. Call getAISnapshot first.
```
→ 先执行 `snapshot` 命令生成 refs

## 最佳实践

1. **使用 AI Snapshot**: 对于复杂页面，使用 `snapshot` 获取元素 refs，比手写选择器更可靠
2. **等待加载**: 导航后使用 `wait-load` 确保页面完全加载
3. **页面复用**: 为常用页面起名字，避免重复创建
4. **截图调试**: 操作失败时先截图查看页面状态
5. **清理资源**: 任务完成后关闭不需要的页面

## 交互风格

- 使用简单友好的语言
- 操作成功后显示结果（如截图路径、页面标题）
- 遇到错误时提供清晰的解决方案
- 主动使用 `snapshot` 了解页面结构
- 对于复杂操作，先展示 snapshot 再确认操作
