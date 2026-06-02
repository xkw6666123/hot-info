export async function onRequest(context) {
  const GITHUB_PAT = context.env.GITHUB_PAT;
  if (!GITHUB_PAT) {
    return new Response(JSON.stringify({ ok: false, msg: '未配置 GITHUB_PAT 环境变量' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  }
  try {
    const resp = await fetch(
      'https://api.github.com/repos/xkw6666123/hot-info/actions/workflows/auto-update.yml/dispatches',
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${GITHUB_PAT}`,
          'Accept': 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
          'Content-Type': 'application/json',
          'User-Agent': 'hot-info-pages',
        },
        body: JSON.stringify({ ref: 'main' }),
      }
    );
    if (resp.status === 204) {
      return new Response(JSON.stringify({ ok: true, msg: 'Actions 已触发！1-2分钟后刷新页面' }), {
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      });
    }
    const err = await resp.text().slice(0, 300);
    return new Response(JSON.stringify({ ok: false, msg: `触发失败(${resp.status})` }), {
      status: resp.status,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, msg: `网络错误: ${e.message}` }), {
      status: 502,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  }
}
