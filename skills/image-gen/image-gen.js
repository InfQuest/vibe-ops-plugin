#!/usr/bin/env node

const https = require('https');
const fs = require('fs');
const path = require('path');

// 配置
const API_KEY = process.env.OPENROUTER_API_KEY;
const MODEL = process.argv[2] || 'gemini-pro';
const PROMPT = process.argv[3] || 'A beautiful sunset over mountains';
const ASPECT_RATIO = process.argv[4] || '1:1';
const NUM_IMAGES = parseInt(process.argv[5]) || 1;
const OUTPUT_DIR = process.argv[6] || '.';
const INPUT_IMAGE = process.argv[7] || '';  // 可选：输入图片路径，用于图片编辑

// 模型映射
const MODEL_MAP = {
  'gemini-pro': 'google/gemini-2.5-flash-image',
  'seedream': 'bytedance-seed/seedream-4.5'
};

const modelId = MODEL_MAP[MODEL] || MODEL;

// 检查 API Key
if (!API_KEY) {
  console.error('❌ 缺少 OPENROUTER_API_KEY 环境变量');
  process.exit(1);
}

console.log(`🎨 开始生成图片...`);
console.log(`📝 提示词: ${PROMPT}`);
console.log(`🤖 模型: ${modelId}`);
console.log(`📐 比例: ${ASPECT_RATIO}`);
console.log(`🔢 数量: ${NUM_IMAGES}`);
if (INPUT_IMAGE) {
  console.log(`🖼️  输入图片: ${INPUT_IMAGE}`);
}

// 构建消息内容
let messageContent;

if (INPUT_IMAGE) {
  // 图片编辑模式：读取输入图片并转为 base64
  if (!fs.existsSync(INPUT_IMAGE)) {
    console.error(`❌ 输入图片不存在: ${INPUT_IMAGE}`);
    process.exit(1);
  }

  const imageBuffer = fs.readFileSync(INPUT_IMAGE);
  const base64Image = imageBuffer.toString('base64');
  const ext = path.extname(INPUT_IMAGE).toLowerCase().slice(1);
  const mimeType = ext === 'jpg' ? 'image/jpeg' : `image/${ext}`;

  messageContent = [
    {
      type: 'text',
      text: `Edit this image: ${PROMPT}`
    },
    {
      type: 'image_url',
      image_url: {
        url: `data:${mimeType};base64,${base64Image}`
      }
    }
  ];
} else {
  // 纯文本生成模式
  messageContent = `Generate an image: ${PROMPT}`;
}

// 使用 chat completions API 生成图片
const requestData = JSON.stringify({
  model: modelId,
  messages: [
    {
      role: 'user',
      content: messageContent
    }
  ],
  modalities: ['image', 'text'],
  image_config: {
    aspect_ratio: ASPECT_RATIO
  },
  max_tokens: 4096
});

const options = {
  hostname: 'openrouter.ai',
  port: 443,
  path: '/api/v1/chat/completions',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${API_KEY}`
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

      // 检查响应格式
      if (!response.choices || response.choices.length === 0) {
        console.error('❌ 未能生成图片');
        console.error('响应:', JSON.stringify(response, null, 2));
        process.exit(1);
      }

      const message = response.choices[0].message;
      const timestamp = Date.now();
      let imageCount = 0;

      // 处理 images 数组（OpenRouter Gemini 格式）
      if (Array.isArray(message.images)) {
        message.images.forEach((item, index) => {
          if (item.type === 'image_url' && item.image_url?.url) {
            const base64Match = item.image_url.url.match(/^data:image\/(\w+);base64,(.+)$/);
            if (base64Match) {
              const ext = base64Match[1] === 'jpeg' ? 'jpg' : base64Match[1];
              const base64Data = base64Match[2];
              const filename = NUM_IMAGES === 1
                ? `generated_image_${timestamp}.${ext}`
                : `generated_image_${timestamp}_${index + 1}.${ext}`;
              const filepath = path.join(OUTPUT_DIR, filename);

              const imageBuffer = Buffer.from(base64Data, 'base64');
              fs.writeFileSync(filepath, imageBuffer);
              console.log(`✅ 图片已保存: ${filepath}`);
              imageCount++;
            }
          }
        });
      }

      // 处理 content 数组（其他模型格式）
      if (imageCount === 0 && Array.isArray(message.content)) {
        message.content.forEach((item, index) => {
          if (item.type === 'image_url' && item.image_url?.url) {
            const base64Match = item.image_url.url.match(/^data:image\/(\w+);base64,(.+)$/);
            if (base64Match) {
              const ext = base64Match[1] === 'jpeg' ? 'jpg' : base64Match[1];
              const base64Data = base64Match[2];
              const filename = `generated_image_${timestamp}_${index + 1}.${ext}`;
              const filepath = path.join(OUTPUT_DIR, filename);

              const imageBuffer = Buffer.from(base64Data, 'base64');
              fs.writeFileSync(filepath, imageBuffer);
              console.log(`✅ 图片已保存: ${filepath}`);
              imageCount++;
            }
          }
        });
      }

      if (imageCount === 0) {
        console.log('ℹ️  未找到图片，响应内容:');
        console.log(message.content || '(空)');
      } else {
        console.log(`\n🎉 完成！共生成 ${imageCount} 张图片`);
      }

    } catch (e) {
      console.error('❌ 解析响应失败:', e.message);
      console.error('原始响应:', data.substring(0, 500));
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
