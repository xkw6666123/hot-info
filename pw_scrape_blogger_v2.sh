#!/usr/bin/env bash
# 免费抖音博主视频批量抓取脚本 (v2 - 防限流版)
# 用法: bash pw_scrape_blogger_v2.sh <博主1> <sec_uid1> [博主2] [sec_uid2] ...
# 输出: stdout → JSON格式 {"博主名": [视频列表], ...}
# 
# 优化：单次浏览器会话抓所有博主 + 随机延迟 + 滚动模拟 + 重试

PCLI="${PLAYWRIGHT_CLI:-playwright-cli}"
PERSIST_DIR="${PW_PERSIST_DIR:-/tmp/pw_douyin_profile}"

# 确保有参数
if [ $# -lt 2 ]; then
    echo '{}' 
    exit 0
fi

declare -A RESULTS
BLOGGERS=()
SEC_UIDS=()

# 解析参数
while [ $# -gt 0 ]; do
    BLOGGERS+=("$1")
    SEC_UIDS+=("$2")
    shift 2
done

unset NODE_OPTIONS
$PCLI kill-all >/dev/null 2>&1
sleep 2

# 步骤1: 打开浏览器（持久化会话，保留cookie）
echo "🔧 启动浏览器..." >&2
$PCLI open --persistent --profile="$PERSIST_DIR" "https://www.douyin.com/" >/dev/null 2>&1
sleep 8

# 检查是否被拦截
TITLE=$($PCLI eval 'document.title' 2>/dev/null | grep -oP '"([^"]+)"' | head -1 | tr -d '"')
if echo "$TITLE" | grep -qi "验证码"; then
    echo "❌ 验证码拦截，稍后重试" >&2
    $PCLI close >/dev/null 2>&1
    exit 1
fi

echo "✅ 页面加载完成" >&2

# 步骤2: 逐个博主抓取
TOTAL=${#BLOGGERS[@]}
for ((i=0; i<TOTAL; i++)); do
    NAME="${BLOGGERS[$i]}"
    UID="${SEC_UIDS[$i]}"
    
    echo "📹 [$((i+1))/$TOTAL] $NAME..." >&2
    
    # 随机延迟 3-8秒（模拟人类操作间隔）
    DELAY=$(( RANDOM % 6 + 3 ))
    sleep $DELAY
    
    # 导航到博主主页
    $PCLI goto "https://www.douyin.com/user/$UID" >/dev/null 2>&1
    sleep 10  # 等页面加载
    
    # 模拟人类滚动：随机滚动几次
    $PCLI eval '
    (function(){
        var s = '$(($RANDOM % 500 + 300))';
        window.scrollBy(0, s);
    })()' >/dev/null 2>&1
    sleep 2
    
    # 提取视频列表
    VIDEOS=$($PCLI eval '
    (function(){
        var r=[],s={};
        var postList = document.querySelector("[data-e2e=\"user-post-list\"]") 
                   || document.querySelector(".route-home");
        var scope = postList || document;
        
        scope.querySelectorAll("a[href*=\"/video/\"]").forEach(function(a){
            var m=a.href.match(/video\/(\d+)/);
            if(!m||s[m[1]])return;
            s[m[1]]=true;
            var t=(a.textContent||"").trim().replace(/\s+/g," ").substring(0,200);
            if(t.length<3) return;
            var likes=0;
            var likeEl=a.closest("[class*=\"item\"]")?a.closest("[class*=\"item\"]").querySelector("[class*=\"count\"]"):null;
            if(likeEl){var lk=likeEl.textContent.match(/([\d.]+)万?/);if(lk){var n=parseFloat(lk[1]);likes=lk[0].indexOf("万")>0?Math.round(n*10000):Math.round(n);}}
            r.push({id:m[1],title:t,url:a.href,likes:likes});
        });
        return JSON.stringify(r.slice(0,8));
    })()' 2>/dev/null)
    
    if [ -z "$VIDEOS" ] || [ "$VIDEOS" = "[]" ]; then
        echo "  ⚠️ 未获取到视频" >&2
        RESULTS["$NAME"]="[]"
    else
        echo "  ✅ $(echo "$VIDEOS" | python3 -c 'import json,sys;print(len(json.load(sys.stdin)))' 2>/dev/null || echo '?')条" >&2
        RESULTS["$NAME"]="$VIDEOS"
    fi
done

# 步骤3: 输出JSON结果并关闭
$PCLI close >/dev/null 2>&1

echo "{" 
FIRST=true
for NAME in "${BLOGGERS[@]}"; do
    if [ "$FIRST" = true ]; then FIRST=false; else echo ","; fi
    echo -n "  \"$NAME\": ${RESULTS[$NAME]}"
done
echo ""
echo "}"
