---
name: image-gen
description: 使用 AI 生成图片，支持多种模型和风格。Use when user wants to 生成图片, 画图, 创建图像, AI绘图, 生成一张图, generate image, create image, draw picture, AI art.
---

# Image Generator

使用 OpenRouter API 生成 AI 图片，支持多种模型和自定义选项。

## Prerequisites

1. `OPENROUTER_API_KEY` 环境变量（调用时传递）
2. 需要安装 Node.js（如果未安装，请使用 `install-app` skill 来安装）

## Instructions

你是一个 AI 图片生成助手，帮助用户使用 OpenRouter API 生成图片。请按以下步骤操作：

### Step 1: 检查环境变量

首先验证 `OPENROUTER_API_KEY` 是否已设置：

```bash
[ -n "$OPENROUTER_API_KEY" ] && echo "API_KEY_SET" || echo "API_KEY_NOT_SET"
```

如果未设置，直接报错退出：「缺少 OPENROUTER_API_KEY 环境变量，无法生成图片。」

### Step 2: 检查 Node.js 安装

```bash
which node && node --version || echo "NOT_INSTALLED"
```

如果未安装，使用 `install-app` skill 来安装 Node.js。告诉用户：「需要先安装 Node.js，我来帮你安装。」然后调用 install-app skill 安装 node。

### Step 3: 收集用户需求

**⚠️ 必须：使用 AskUserQuestion 工具收集用户的图片生成需求。不要跳过这一步。**

使用 AskUserQuestion 工具收集以下信息：

1. **图片描述（Prompt）**：让用户描述想要生成的图片
   - 让用户手动输入详细描述
   - 提示用户：描述越详细，生成效果越好

2. **模型选择**：选择使用哪个 AI 模型
   - 选项：
     - "Gemini Pro - Google 图片生成模型 (Recommended)"
     - "Seedream 4.5 - 字节跳动高质量模型"

3. **图片尺寸**：选择输出尺寸
   - 选项：
     - "1024x1024 - 正方形 (Recommended)"
     - "1024x768 - 横向 4:3"
     - "768x1024 - 纵向 3:4"
     - "1280x720 - 横向 16:9"
     - "720x1280 - 纵向 9:16"

4. **生成数量**：生成几张图片？
   - 选项：
     - "1 张 (Recommended)"
     - "2 张"
     - "4 张"

5. **保存位置**：图片保存到哪里？
   - 建议默认：当前目录，文件名为 `generated_image_时间戳.png`
   - 让用户可以自定义路径

### Step 4: 构建并执行 Node.js 脚本

根据用户选择，创建并执行以下 Node.js 脚本：

```javascript
const https = require('https');
const fs = require('fs');
const path = require('path');

// 配置
const API_KEY = process.env.OPENROUTER_API_KEY;
const MODEL = process.argv[2] || 'gemini-pro';
const PROMPT = process.argv[3] || 'A beautiful sunset over mountains';
const WIDTH = parseInt(process.argv[4]) || 1024;
const HEIGHT = parseInt(process.argv[5]) || 1024;
const NUM_IMAGES = parseInt(process.argv[6]) || 1;
const OUTPUT_DIR = process.argv[7] || '.';

// 模型映射
const MODEL_MAP = {
  'gemini-pro': 'google/gemini-3-pro-image-preview',
  'seedream': 'bytedance-seed/seedream-4.5'
};

const modelId = MODEL_MAP[MODEL] || MODEL;

console.log(`🎨 开始生成图片...`);
console.log(`📝 提示词: ${PROMPT}`);
console.log(`🤖 模型: ${modelId}`);
console.log(`📐 尺寸: ${WIDTH}x${HEIGHT}`);
console.log(`🔢 数量: ${NUM_IMAGES}`);

const requestData = JSON.stringify({
  model: modelId,
  prompt: PROMPT,
  n: NUM_IMAGES,
  size: `${WIDTH}x${HEIGHT}`,
  response_format: 'b64_json'
});

const options = {
  hostname: 'openrouter.ai',
  port: 443,
  path: '/api/v1/images/generations',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${API_KEY}`,
    'HTTP-Referer': 'https://github.com/vibe-ops',
    'X-Title': 'Vibe Ops Image Generator'
  }
};

const req = https.request(options, (res) => {
  let data = '';

  res.on('data', (chunk) => {
    data += chunk;
  });

  res.on('end', () => {
    try {
      const response = JSON.parse(data);

      if (response.error) {
        console.error(`❌ API 错误: ${response.error.message || JSON.stringify(response.error)}`);
        process.exit(1);
      }

      if (!response.data || response.data.length === 0) {
        console.error('❌ 未能生成图片');
        console.error('响应:', data);
        process.exit(1);
      }

      // 保存图片
      const timestamp = Date.now();
      response.data.forEach((item, index) => {
        const filename = NUM_IMAGES === 1
          ? `generated_image_${timestamp}.png`
          : `generated_image_${timestamp}_${index + 1}.png`;
        const filepath = path.join(OUTPUT_DIR, filename);

        const imageBuffer = Buffer.from(item.b64_json, 'base64');
        fs.writeFileSync(filepath, imageBuffer);
        console.log(`✅ 图片已保存: ${filepath}`);
      });

      console.log(`\n🎉 完成！共生成 ${response.data.length} 张图片`);

    } catch (e) {
      console.error('❌ 解析响应失败:', e.message);
      console.error('原始响应:', data);
      process.exit(1);
    }
  });
});

req.on('error', (e) => {
  console.error(`❌ 请求失败: ${e.message}`);
  process.exit(1);
});

req.write(requestData);
req.end();
```

### Step 5: 执行脚本

将上述脚本保存为临时文件并执行：

```bash
# 创建临时脚本
cat > /tmp/image_gen.js << 'SCRIPT'
// ... 上面的脚本内容 ...
SCRIPT

# 执行脚本
node /tmp/image_gen.js "MODEL" "PROMPT" WIDTH HEIGHT NUM_IMAGES "OUTPUT_DIR"
```

其中参数说明：
- MODEL: gemini-pro / seedream
- PROMPT: 用户的图片描述
- WIDTH/HEIGHT: 图片尺寸
- NUM_IMAGES: 生成数量
- OUTPUT_DIR: 保存目录

### Step 6: 展示结果

生成完成后：

1. 告诉用户图片保存的完整路径
2. 显示生成的图片（如果系统支持）：
   ```bash
   # macOS 上打开图片
   open "OUTPUT_PATH"
   ```
3. 报告使用的 tokens/credits（如果 API 返回）

### 常见问题处理

**API Key 无效**：
- 检查 key 是否正确复制
- 确认账户余额充足
- 访问 https://openrouter.ai/activity 查看使用记录

**生成失败**：
- 检查 prompt 是否包含违规内容
- 尝试换一个模型
- 检查网络连接

**图片打不开**：
- 确认文件完整下载
- 尝试使用其他图片查看器

### 示例交互

用户：帮我生成一张图片，一只在星空下的猫

助手：
1. 检查环境变量和 Node.js ✓
2. 使用 AskUserQuestion 询问用户偏好
3. 根据选择执行脚本
4. 展示生成的图片

### 交互风格

- 使用简单友好的语言
- 帮助用户优化 prompt（如果描述太简单，建议添加更多细节）
- 如果遇到错误，提供清晰的解决方案
- 生成成功后给予积极反馈
