#!/usr/bin/env bash
# 抖音用户搜索：按名称查找 sec_uid
# 用法: bash pw_search_user.sh <用户名>
# 输出: sec_uid (单行) 或空

NAME="$1"
PCLI="${PLAYWRIGHT_CLI:-playwright-cli}"

if [ -z "$NAME" ]; then
    exit 0
fi

unset NODE_OPTIONS
$PCLI kill-all >/dev/null 2>&1
sleep 2

# 编码用户名用于URL
ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$NAME'))" 2>/dev/null || echo "$NAME")

$PCLI open "https://www.douyin.com/search/${ENCODED}?type=user" >/dev/null 2>&1
sleep 8

# 检查验证码
TITLE=$($PCLI eval 'document.title' 2>/dev/null | grep -oP '"([^"]+)"' | head -1 | tr -d '"')
if echo "$TITLE" | grep -qi "验证码"; then
    echo "" >&2
    echo "验证码拦截" >&2
    $PCLI close >/dev/null 2>&1
    exit 0
fi

# 提取第一个用户链接中的 sec_uid
$PCLI eval '
(function(){
    var links = document.querySelectorAll("a[href*=\"/user/\"]");
    for (var i = 0; i < links.length; i++) {
        var m = links[i].href.match(/\/user\/([^?&#]+)/);
        if (m && m[1]) {
            return m[1];
        }
    }
    return "";
})()' 2>/dev/null | grep -oP 'MS4w[^"]*' | head -1

$PCLI close >/dev/null 2>&1
