#!/usr/bin/env node

const https = require('https');
const fs = require('fs');
const path = require('path');

// 配置
const API_KEY = process.env.AIHUBMIX_API_KEY;
const BASE_URL = 'aihubmix.com';

// 命令行参数
const MODEL = process.argv[2] || 'veo-3.1';
const PROMPT = process.argv[3] || 'A cat sitting on a windowsill';
const SIZE = process.argv[4] || '720P';
const SECONDS = process.argv[5] || '8';
const OUTPUT_DIR = process.argv[6] || '.';
const INPUT_IMAGE = process.argv[7] || '';

// 模型映射
const MODEL_MAP = {
  'veo-3.1': 'veo-3.1-generate-preview',
  'sora-2-pro': 'sora-2-pro',
};

// 支持图片输入的模型
const IMAGE_SUPPORTED_MODELS = ['sora-2-pro'];

// 所有图片上传都需要 multipart/form-data（不是 base64）

const modelId = MODEL_MAP[MODEL] || MODEL;

// 检查 API Key
if (!API_KEY) {
  console.error('Error: Missing AIHUBMIX_API_KEY environment variable');
  process.exit(1);
}

console.log(`[VideoGen] Starting video generation...`);
console.log(`[Config] Model: ${modelId}`);
console.log(`[Config] Prompt: ${PROMPT}`);
console.log(`[Config] Size: ${SIZE}`);
console.log(`[Config] Duration: ${SECONDS}s`);
if (INPUT_IMAGE) {
  console.log(`[Config] Input image: ${INPUT_IMAGE}`);
}
console.log('');

// 辅助函数：发送 HTTPS 请求
function request(options, data) {
  return new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try {
          if (res.headers['content-type']?.includes('application/json')) {
            resolve({ status: res.statusCode, data: JSON.parse(body) });
          } else {
            resolve({ status: res.statusCode, data: body, raw: true });
          }
        } catch (e) {
          resolve({ status: res.statusCode, data: body, raw: true });
        }
      });
    });
    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

// 辅助函数：等待
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// 构建 multipart/form-data 请求体
function buildMultipartBody(fields, file) {
  const boundary = '----FormBoundary' + Math.random().toString(36).substring(2);
  const parts = [];

  // 添加普通字段
  for (const [key, value] of Object.entries(fields)) {
    parts.push(
      `--${boundary}\r\n` +
      `Content-Disposition: form-data; name="${key}"\r\n\r\n` +
      `${value}\r\n`
    );
  }

  // 添加文件字段
  if (file) {
    const ext = path.extname(file.path).toLowerCase().slice(1);
    const mimeType = ext === 'jpg' ? 'image/jpeg' : `image/${ext}`;
    parts.push(
      `--${boundary}\r\n` +
      `Content-Disposition: form-data; name="${file.fieldName}"; filename="${path.basename(file.path)}"\r\n` +
      `Content-Type: ${mimeType}\r\n\r\n`
    );
  }

  const header = Buffer.from(parts.join(''));
  const footer = Buffer.from(`\r\n--${boundary}--\r\n`);

  if (file) {
    const fileContent = fs.readFileSync(file.path);
    return {
      body: Buffer.concat([header, fileContent, footer]),
      contentType: `multipart/form-data; boundary=${boundary}`
    };
  } else {
    return {
      body: Buffer.concat([header, footer]),
      contentType: `multipart/form-data; boundary=${boundary}`
    };
  }
}

// 主函数
async function main() {
  try {
    // Step 1: 创建视频生成任务
    console.log('[Step 1] Creating video generation task...');

    let requestBody;
    let contentType = 'application/json';

    // 检查是否需要上传图片
    if (INPUT_IMAGE && IMAGE_SUPPORTED_MODELS.includes(modelId)) {
      if (!fs.existsSync(INPUT_IMAGE)) {
        console.error(`Error: Input image not found: ${INPUT_IMAGE}`);
        process.exit(1);
      }

      // 所有图片上传都使用 multipart/form-data
      const multipart = buildMultipartBody(
        { model: modelId, prompt: PROMPT, size: SIZE, seconds: SECONDS },
        { fieldName: 'input_reference', path: INPUT_IMAGE }
      );
      requestBody = multipart.body;
      contentType = multipart.contentType;
    } else {
      if (INPUT_IMAGE && !IMAGE_SUPPORTED_MODELS.includes(modelId)) {
        console.warn(`[Warning] Model ${modelId} does not support image input, ignoring input image`);
      }

      requestBody = JSON.stringify({
        model: modelId,
        prompt: PROMPT,
        size: SIZE,
        seconds: SECONDS
      });
    }

    const createOptions = {
      hostname: BASE_URL,
      port: 443,
      path: '/v1/videos',
      method: 'POST',
      headers: {
        'Content-Type': contentType,
        'Authorization': `Bearer ${API_KEY}`,
        'Content-Length': Buffer.byteLength(requestBody)
      }
    };

    const createResponse = await request(createOptions, requestBody);

    if (createResponse.status !== 200 && createResponse.status !== 201) {
      console.error(`Error: Failed to create task: ${JSON.stringify(createResponse.data)}`);
      process.exit(1);
    }

    const videoId = createResponse.data.id;
    console.log(`[Step 1] Task created: ${videoId}`);
    console.log('');

    // Step 2: 轮询状态
    console.log('[Step 2] Waiting for video generation...');
    const startTime = Date.now();
    const maxWaitTime = 20 * 60 * 1000; // 20 分钟
    const pollInterval = 10 * 1000; // 10 秒

    let lastStatus = '';
    while (Date.now() - startTime < maxWaitTime) {
      const statusOptions = {
        hostname: BASE_URL,
        port: 443,
        path: `/v1/videos/${videoId}`,
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${API_KEY}`
        }
      };

      const statusResponse = await request(statusOptions);

      if (statusResponse.status !== 200) {
        console.error(`Error: Failed to get status: ${JSON.stringify(statusResponse.data)}`);
        await sleep(pollInterval);
        continue;
      }

      const status = statusResponse.data.status?.toLowerCase();
      const elapsed = Math.round((Date.now() - startTime) / 1000);

      if (status !== lastStatus) {
        console.log(`[Status] ${status} (${elapsed}s elapsed)`);
        lastStatus = status;
      }

      if (status === 'completed' || status === 'done' || status === 'success') {
        console.log(`[Step 2] Video generation completed!`);
        console.log('');
        break;
      }

      if (status === 'failed' || status === 'error') {
        const errorDetail = statusResponse.data.error
          ? (typeof statusResponse.data.error === 'object' ? JSON.stringify(statusResponse.data.error) : statusResponse.data.error)
          : JSON.stringify(statusResponse.data);
        console.error(`Error: Video generation failed: ${errorDetail}`);
        process.exit(1);
      }

      await sleep(pollInterval);
    }

    if (Date.now() - startTime >= maxWaitTime) {
      console.error('Error: Video generation timed out (20 minutes)');
      process.exit(1);
    }

    // Step 3: 下载视频
    console.log('[Step 3] Downloading video...');

    const timestamp = Date.now();
    const filename = `generated_video_${timestamp}.mp4`;
    const filepath = path.join(OUTPUT_DIR, filename);

    const downloadUrl = `https://${BASE_URL}/v1/videos/${videoId}/content`;

    // 直接下载二进制内容
    await new Promise((resolve, reject) => {
      const file = fs.createWriteStream(filepath);

      const downloadOptions = {
        hostname: BASE_URL,
        port: 443,
        path: `/v1/videos/${videoId}/content`,
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${API_KEY}`
        }
      };

      const req = https.request(downloadOptions, (res) => {
        if (res.statusCode === 302 || res.statusCode === 301) {
          // 处理重定向
          const redirectUrl = new URL(res.headers.location);
          https.get(res.headers.location, (redirectRes) => {
            redirectRes.pipe(file);
            file.on('finish', () => {
              file.close();
              resolve();
            });
          }).on('error', reject);
        } else if (res.statusCode === 200) {
          res.pipe(file);
          file.on('finish', () => {
            file.close();
            resolve();
          });
        } else {
          reject(new Error(`Download failed with status ${res.statusCode}`));
        }
      });

      req.on('error', reject);
      req.end();
    });

    const stats = fs.statSync(filepath);
    const fileSizeMB = (stats.size / (1024 * 1024)).toFixed(2);
    const totalTime = Math.round((Date.now() - startTime) / 1000);

    console.log(`[Step 3] Video downloaded: ${filepath}`);
    console.log('');
    console.log('='.repeat(50));
    console.log(`Video saved: ${filepath}`);
    console.log(`File size: ${fileSizeMB} MB`);
    console.log(`Total time: ${totalTime}s`);
    console.log('='.repeat(50));

  } catch (error) {
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }
}

main();
