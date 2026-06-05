#!/usr/bin/env bash
# 免费抖音博主视频抓取脚本
# 用法: bash pw_scrape_blogger.sh <博主名> <sec_uid>
# 输出: stdout → JSON格式视频列表, stderr → 日志

NAME="$1"
SEC_UID="$2"
PCLI="${PLAYWRIGHT_CLI:-playwright-cli}"

if [ -z "$SEC_UID" ]; then
    echo '[]'
    exit 0
fi

# 清理旧会话
unset NODE_OPTIONS
$PCLI kill-all >/dev/null 2>&1
sleep 2

# 打开博主主页
$PCLI open "https://www.douyin.com/user/$SEC_UID" >/dev/null 2>&1
sleep 12  # 等抖音页面完全加载（含视频列表异步渲染）

# 检查是否弹了验证码
TITLE=$($PCLI eval 'document.title' 2>/dev/null | grep -oP '"([^"]+)"' | head -1 | tr -d '"')
if echo "$TITLE" | grep -qi "验证码"; then
    echo '[]' >&2
    echo "验证码拦截: $TITLE" >&2
    $PCLI close >/dev/null 2>&1
    exit 0
fi

# 提取视频列表
$PCLI eval '
(function(){
    var r=[],s={};
    document.querySelectorAll("a[href*=\"/video/\"]").forEach(function(a){
        var m=a.href.match(/video\/(\d+)/);
        if(!m||s[m[1]])return;
        s[m[1]]=true;
        var t=(a.textContent||"").trim().replace(/\s+/g," ").substring(0,120);
        r.push({id:m[1],title:t,url:a.href});
    });
    return JSON.stringify(r.slice(0,8));
})()' 2>/dev/null

$PCLI close >/dev/null 2>&1
