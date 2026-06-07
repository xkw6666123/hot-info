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

# 提取博主本人的视频列表（优先获取标题+点赞+话题标签）
$PCLI eval '
(function(){
    var r=[],s={};
    // 优先用作品列表容器
    var postList = document.querySelector("[data-e2e=\"user-post-list\"]") 
               || document.querySelector(".route-home") 
               || document.querySelector("[class*=\"post\"]");
    var scope = postList || document;
    
    scope.querySelectorAll("a[href*=\"/video/\"]").forEach(function(a){
        var m=a.href.match(/video\/(\d+)/);
        if(!m||s[m[1]])return;
        s[m[1]]=true;
        // 提取标题（清理多余空格和特殊字符）
        var t=(a.textContent||"").trim().replace(/\s+/g," ").substring(0,200);
        if(t.length<3) return;
        // 尝试提取点赞数（从附近的span中）
        var likeEl=a.parentElement? a.parentElement.querySelector("[class*=\"count\"], [class*=\"like\"]") : null;
        var likes=0;
        if(likeEl){var lk=likeEl.textContent.match(/([\d.]+)万?/);if(lk){var n=parseFloat(lk[1]);likes=lk[0].indexOf("万")>0?Math.round(n*10000):Math.round(n);}}
        r.push({id:m[1],title:t,url:a.href,likes:likes});
    });
    return JSON.stringify(r.slice(0,8));
})()' 2>/dev/null

$PCLI close >/dev/null 2>&1
