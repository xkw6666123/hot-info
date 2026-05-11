#!/bin/bash
# 批量提取抖音视频描述 → 更新 data.json
# 用法: bash extract_descs.sh

PCLI="unset NODE_OPTIONS && playwright-cli"
WORK="C:/Users/Kevin/WorkBuddy/2026-05-08-task-5/hot-info"
TMPDIR="$WORK/desc_tmp"
mkdir -p "$TMPDIR"

echo "=== 批量提取视频描述 ==="

# 视频ID和URL列表（从Python生成）
cat << 'VIDEOS' > "$TMPDIR/videos.txt"
882068945|https://www.douyin.com/video/7638407920689909026
130397889|https://www.douyin.com/video/7637659979633265972
461384607|https://www.douyin.com/video/7637292553041136911
351002511|https://www.douyin.com/video/7637886711091793081
959389967|https://www.douyin.com/video/7637158565535043493
570114856|https://www.douyin.com/video/7637501246966402803
676597854|https://www.douyin.com/video/7637573042922907569
742378366|https://www.douyin.com/video/7637137991799134073
844792692|https://www.douyin.com/video/7636380086177949553
542356449|https://www.douyin.com/video/7637937638381136369
584540481|https://www.douyin.com/video/7637470030146135674
756039338|https://www.douyin.com/video/7637070816811280315
7637523554896069753|https://www.douyin.com/video/7637523554896069753
7637946752192457334|https://www.douyin.com/video/7637946752192457334
7637163836483684836|https://www.douyin.com/video/7637163836483684836
901879377|https://www.bilibili.com/video/BV17W5b6nEXY
VIDEOS

total=16
n=0
while IFS='|' read -r vid url; do
  n=$((n+1))
  echo "[$n/$total] ID=$vid"
  
  bash -c "$PCLI open \"$url\"" 2>&1 | tail -1
  sleep 7
  
  # 滚动加载描述
  bash -c "$PCLI eval 'window.scrollTo(0,800)'" 2>&1 | tail -1
  sleep 3
  
  # 提取描述文本
  desc=$(bash -c "$PCLI eval \"(function(){var t=document.body.innerText;var i=t.indexOf('作者声明');if(i<0)i=t.indexOf('发布时间');if(i<0)return'';var s=t.substring(i);return s.split('\\\\n').filter(function(l){return l.trim().length>15&&!/发布时间|粉丝|获赞|登录|合集|第\\\\d+集/.test(l.trim());}).slice(0,6).join('\\\\n');})()\"" 2>&1 | grep "Result" -A100 | tail -n +2 | sed 's/^"//;s/"$//' | sed 's/\\n/\n/g')
  
  if [ -n "$desc" ] && [ ${#desc} -gt 20 ]; then
    echo "$desc" > "$TMPDIR/${vid}.txt"
    echo "  ✅ ${#desc}字"
  else
    echo "  ⚠️ 未提取到"
    echo "" > "$TMPDIR/${vid}.txt"
  fi
  
  bash -c "$PCLI close" 2>&1 | tail -1
  echo ""
done < "$TMPDIR/videos.txt"

echo "=== 提取完成，开始更新 data.json ==="
bash -c "unset NODE_OPTIONS && C:/Users/Kevin/AppData/Local/Programs/Python/Python311/python.exe $WORK/update_intros_from_files.py $TMPDIR"
echo "=== 完成 ==="
