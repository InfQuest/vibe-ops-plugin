#!/usr/bin/env node

const https = require('https');
const fs = require('fs');
const path = require('path');

// 配置
const API_KEY = process.env.OPENROUTER_API_KEY;
const IMAGE_PATH = process.argv[2];
const PROMPT = process.argv[3] || '请描述这张图片的内容';
const LANGUAGE = process.argv[4] || 'chinese';

// 使用 Gemini 3 Pro Preview
const MODEL_ID = 'google/gemini-3-pro-preview';

// 检查参数
if (!IMAGE_PATH) {
  console.error('❌ 请提供图片路径');
  console.error('用法: node image-understand.js <图片路径> [问题] [语言]');
  process.exit(1);
}

// 检查 API Key
if (!API_KEY) {
  console.error('❌ 缺少 OPENROUTER_API_KEY 环境变量');
  process.exit(1);
}

// 检查图片文件是否存在
if (!fs.existsSync(IMAGE_PATH)) {
  console.error(`❌ 图片文件不存在: ${IMAGE_PATH}`);
  process.exit(1);
}

// 读取图片并转为 base64
const imageBuffer = fs.readFileSync(IMAGE_PATH);
const base64Image = imageBuffer.toString('base64');
const ext = path.extname(IMAGE_PATH).toLowerCase().slice(1);
const mimeType = ext === 'jpg' ? 'image/jpeg' : `image/${ext}`;

// 构建系统提示
const systemPrompt = LANGUAGE === 'chinese'
  ? '你是一个专业的图片分析助手。请用中文回答用户关于图片的问题，回答要详细、准确、有条理。'
  : 'You are a professional image analysis assistant. Please answer user questions about images in English with detailed, accurate, and well-organized responses.';

console.log(`🔍 开始分析图片...`);
console.log(`📷 图片: ${IMAGE_PATH}`);
console.log(`❓ 问题: ${PROMPT}`);
console.log(`🤖 模型: ${MODEL_ID}`);
console.log(`🌐 语言: ${LANGUAGE === 'chinese' ? '中文' : 'English'}`);
console.log('');

// 构建请求
const requestData = JSON.stringify({
  model: MODEL_ID,
  messages: [
    {
      role: 'system',
      content: systemPrompt
    },
    {
      role: 'user',
      content: [
        {
          type: 'text',
          text: PROMPT
        },
        {
          type: 'image_url',
          image_url: {
            url: `data:${mimeType};base64,${base64Image}`
          }
        }
      ]
    }
  ],
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
        console.error('❌ 未能获取分析结果');
        console.error('响应:', JSON.stringify(response, null, 2));
        process.exit(1);
      }

      const message = response.choices[0].message;
      const content = message.content;

      console.log('━'.repeat(50));
      console.log('📋 分析结果:');
      console.log('━'.repeat(50));
      console.log('');
      console.log(content);
      console.log('');
      console.log('━'.repeat(50));

      // 显示 token 使用情况
      if (response.usage) {
        console.log(`📊 Token 使用: 输入 ${response.usage.prompt_tokens}, 输出 ${response.usage.completion_tokens}`);
      }

      console.log('✅ 分析完成');

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
