#!/usr/bin/env bun

import fs from 'fs';
import path from 'path';

// Config
const API_KEY = process.env.MAX_API_KEY;
const MEDIA_PATH = process.argv[2];
const PROMPT = process.argv[3] || 'Please describe this content';
const LANGUAGE = process.argv[4] || 'chinese';

// Use Gemini 2.5 Flash for multimodal
const MODEL_ID = 'google/gemini-2.5-flash';

// File type detection
const IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp']);
const VIDEO_EXTS = new Set(['mp4', 'mpeg', 'mov', 'webm']);
const AUDIO_EXTS = new Set(['wav', 'mp3', 'aiff', 'aac', 'ogg', 'flac', 'm4a']);

const MIME_TYPES = {
  // Images
  jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png',
  gif: 'image/gif', webp: 'image/webp',
  // Videos
  mp4: 'video/mp4', mpeg: 'video/mpeg', mov: 'video/mov', webm: 'video/webm',
  // Audio
  wav: 'audio/wav', mp3: 'audio/mp3', aiff: 'audio/aiff',
  aac: 'audio/aac', ogg: 'audio/ogg', flac: 'audio/flac', m4a: 'audio/m4a'
};

function getMediaType(filePath) {
  // Check if it's a YouTube URL by parsing and validating the hostname
  try {
    // Only attempt URL parsing if the input looks like a URL
    if (typeof filePath === 'string' &&
        (filePath.startsWith('http://') || filePath.startsWith('https://'))) {
      const url = new URL(filePath);
      const host = url.hostname.toLowerCase();
      const allowedYouTubeHosts = new Set([
        'youtube.com',
        'www.youtube.com',
        'm.youtube.com',
        'youtu.be'
      ]);
      if (allowedYouTubeHosts.has(host)) {
        return 'youtube';
      }
    }
  } catch (e) {
    // If parsing fails, fall through and treat as a file path
  }

  const ext = path.extname(filePath).toLowerCase().slice(1);
  if (IMAGE_EXTS.has(ext)) return 'image';
  if (VIDEO_EXTS.has(ext)) return 'video';
  if (AUDIO_EXTS.has(ext)) return 'audio';
  return null;
}

function getMimeType(filePath) {
  const ext = path.extname(filePath).toLowerCase().slice(1);
  return MIME_TYPES[ext] || 'application/octet-stream';
}

// Check args
if (!MEDIA_PATH) {
  console.error('Usage: bun media-understand.js <media_path_or_youtube_url> [prompt] [language]');
  console.error('');
  console.error('Supported formats:');
  console.error('  Images: jpg, jpeg, png, gif, webp');
  console.error('  Videos: mp4, mpeg, mov, webm (or YouTube URL)');
  console.error('  Audio:  wav, mp3, aiff, aac, ogg, flac, m4a');
  process.exit(1);
}

// Check API Key
if (!API_KEY) {
  console.error('Error: MAX_API_KEY environment variable is required');
  process.exit(1);
}

// Detect media type
const mediaType = getMediaType(MEDIA_PATH);
if (!mediaType) {
  console.error(`Error: Unsupported file format: ${MEDIA_PATH}`);
  console.error('Supported: jpg, png, gif, webp, mp4, mov, webm, wav, mp3, m4a, flac, ogg, aac');
  process.exit(1);
}

// For non-YouTube, check file exists
if (mediaType !== 'youtube') {
  if (!fs.existsSync(MEDIA_PATH)) {
    console.error(`Error: File not found: ${MEDIA_PATH}`);
    process.exit(1);
  }

  // Check file size (limit 100MB for video/audio, 20MB for images)
  const maxSize = mediaType === 'image' ? 20 * 1024 * 1024 : 100 * 1024 * 1024;
  const stats = fs.statSync(MEDIA_PATH);
  if (stats.size > maxSize) {
    const limitMB = maxSize / 1024 / 1024;
    console.error(`Error: File exceeds ${limitMB}MB limit (current: ${(stats.size / 1024 / 1024).toFixed(2)}MB)`);
    process.exit(1);
  }
}

// Build system prompt
const systemPrompt = LANGUAGE === 'chinese'
  ? '你是一个专业的多媒体分析助手。请用中文回答用户关于图片、视频或音频的问题，回答要详细、准确、有条理。'
  : 'You are a professional multimedia analysis assistant. Please answer user questions about images, videos, or audio in English with detailed, accurate, and well-organized responses.';

// Media type labels
const mediaLabels = {
  image: { icon: '🖼️', name: 'Image', nameCN: '图片' },
  video: { icon: '🎬', name: 'Video', nameCN: '视频' },
  audio: { icon: '🎵', name: 'Audio', nameCN: '音频' },
  youtube: { icon: '📺', name: 'YouTube', nameCN: 'YouTube 视频' }
};

const label = mediaLabels[mediaType];
console.log(`🔍 Starting analysis...`);
console.log(`${label.icon} ${label.name}: ${MEDIA_PATH}`);
console.log(`❓ Prompt: ${PROMPT}`);
console.log(`🤖 Model: ${MODEL_ID}`);
console.log(`🌐 Language: ${LANGUAGE === 'chinese' ? '中文' : 'English'}`);
console.log('');

// Build content array based on media type
function buildContent() {
  const content = [{ type: 'text', text: PROMPT }];

  if (mediaType === 'youtube') {
    // YouTube video URL
    content.push({
      type: 'video_url',
      video_url: { url: MEDIA_PATH }
    });
  } else if (mediaType === 'image') {
    // Image: base64 encoded
    const buffer = fs.readFileSync(MEDIA_PATH);
    const base64 = buffer.toString('base64');
    const mimeType = getMimeType(MEDIA_PATH);
    content.push({
      type: 'image_url',
      image_url: { url: `data:${mimeType};base64,${base64}` }
    });
  } else if (mediaType === 'video') {
    // Video: base64 encoded (Note: Gemini via AI Studio only supports YouTube)
    const buffer = fs.readFileSync(MEDIA_PATH);
    const base64 = buffer.toString('base64');
    const mimeType = getMimeType(MEDIA_PATH);
    content.push({
      type: 'video_url',
      video_url: { url: `data:${mimeType};base64,${base64}` }
    });
  } else if (mediaType === 'audio') {
    // Audio: base64 with input_audio format
    const buffer = fs.readFileSync(MEDIA_PATH);
    const base64 = buffer.toString('base64');
    const ext = path.extname(MEDIA_PATH).toLowerCase().slice(1);
    content.push({
      type: 'input_audio',
      input_audio: { data: base64, format: ext }
    });
  }

  return content;
}

// 使用 fetch 调用 API
try {
  const response = await fetch('https://internal.infquest.com/api/openrouter/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_KEY}`
    },
    body: JSON.stringify({
      model: MODEL_ID,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: buildContent() }
      ],
      max_tokens: 4096
    })
  });

  const data = await response.json();

  if (data.error) {
    console.error(`Error: ${data.error.message || JSON.stringify(data.error)}`);
    process.exit(1);
  }

  if (!data.choices || data.choices.length === 0) {
    console.error('Error: No response from API');
    console.error('Response:', JSON.stringify(data, null, 2));
    process.exit(1);
  }

  const content = data.choices[0].message.content;

  console.log('━'.repeat(50));
  console.log('📋 Analysis Result:');
  console.log('━'.repeat(50));
  console.log('');
  console.log(content);
  console.log('');
  console.log('━'.repeat(50));

  if (data.usage) {
    console.log(`📊 Tokens: input ${data.usage.prompt_tokens}, output ${data.usage.completion_tokens}`);
  }

  console.log('✅ Analysis complete');

} catch (e) {
  console.error(`Request failed: ${e.message}`);
  process.exit(1);
}
