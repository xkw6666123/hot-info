#!/usr/bin/env bash
set -e
export PCLI="playwright-cli"
unset NODE_OPTIONS

# 1. 清理旧会话
$PCLI close 2>/dev/null || true
$PCLI kill-all 2>/dev/null || true
sleep 2

# 2. 打开博主主页
$PCLI open "https://www.douyin.com/user/MS4wLjABAAAAptvL9jL0lV_qhvEnHAhZRs5yEekpupXZUwucqRqrhBvMv2XUWQgxBNMRwcIP6Evf" 2>/dev/null
sleep 18

# 3. 找到 aweme/post API 请求的序号
REQ_LINE=$($PCLI requests 2>/dev/null | grep 'aweme/v1/web/aweme/post' | head -1)
if [ -z "$REQ_LINE" ]; then
    echo '[]'
    exit 0
fi
IDX=$(echo "$REQ_LINE" | grep -oP '^\s*\K\d+')

# 4. 获取响应体
$PCLI response-body $IDX 2>/dev/null

# 5. 关闭
$PCLI close 2>/dev/null || true
