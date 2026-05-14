// Cloudflare Pages Function - 一键触发 GitHub Actions 更新
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

    if (resp.ok || resp.status === 204) {
      return new Response(JSON.stringify({ ok: true, msg: '更新已触发，1-2分钟后刷新页面即可看到最新数据' }), {
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      });
    } else {
      const err = await resp.text();
      return new Response(JSON.stringify({ ok: false, msg: `触发失败(${resp.status}): ${err.substring(0, 200)}` }), {
        status: resp.status,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      });
    }
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, msg: `网络错误: ${e.message}` }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  }
}
