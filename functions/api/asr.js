/**
 * Xiaomi MiMo ASR 代理
 * 接收前端录音 → 转发到 MiMo ASR API → 返回识别文本
 * 部署时需在 Cloudflare Pages 设置环境变量 MIMO_API_KEY
 */
export async function onRequest(context) {
  // 处理 CORS 预检
  if (context.request.method === 'OPTIONS') {
    return new Response(null, {
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
      },
    });
  }

  if (context.request.method !== 'POST') {
    return new Response(JSON.stringify({ error: '仅支持 POST' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  }

  const MIMO_API_KEY = context.env.MIMO_API_KEY;
  if (!MIMO_API_KEY) {
    return new Response(JSON.stringify({ error: '未配置 MIMO_API_KEY' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  }

  try {
    const body = await context.request.json();
    const { audio, mimeType, language } = body;

    if (!audio) {
      return new Response(JSON.stringify({ error: '缺少 audio 参数' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      });
    }

    const lang = language || 'zh';
    const mime = mimeType || 'audio/webm';

    // 调用 MiMo ASR API
    const resp = await fetch('https://token-plan-cn.xiaomimimo.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${MIMO_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'mimo-v2.5-asr',
        messages: [
          {
            role: 'user',
            content: [
              {
                type: 'input_audio',
                input_audio: {
                  data: `data:${mime};base64,${audio}`,
                },
              },
            ],
          },
        ],
        asr_options: { language: lang },
        max_tokens: 500,
      }),
    });

    const result = await resp.json();

    // 提取识别文本
    let text = '';
    if (result.choices && result.choices[0] && result.choices[0].message) {
      text = result.choices[0].message.content || '';
    }

    return new Response(JSON.stringify({ text, ok: true }), {
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message, ok: false }), {
      status: 502,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  }
}
