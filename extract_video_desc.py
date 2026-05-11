#!/usr/bin/env python3
"""
最终版：从抖音/B站页面提取视频描述文案
- 有详细描述的（如阿七）：提取完整文案
- 只有标题的：保留标题+话题作为文案
用法：python extract_video_desc.py [--update]
  --update  提取后直接更新 data.json 并重新生成 data.js
"""
import json, subprocess, os, time, re

PCLI = "C:/Users/Kevin/.workbuddy/binaries/node/versions/22.12.0/playwright-cli"
SHELL = "C:/Program Files/Git/bin/bash.exe"
ENV = {**os.environ, "NODE_OPTIONS": "", "PYTHONIOENCODING": "utf-8"}

def bash(cmd, timeout=60):
    r = subprocess.run([SHELL, "-c", cmd], capture_output=True, timeout=timeout, env=ENV)
    return (r.stdout + r.stderr).decode('utf-8', errors='replace')


def extract_desc(url):
    """提取单个视频的描述（通过 bash 调用 playwright-cli）"""
    # 打开
    bash(f'unset NODE_OPTIONS && "{PCLI}" open "{url}"', timeout=40)
    time.sleep(8)
    
    # 滚动
    bash(f'unset NODE_OPTIONS && "{PCLI}" eval "window.scrollTo(0,800)"', timeout=10)
    time.sleep(4)
    
    # 提取：用特殊分隔符避免换行问题
    out = bash(f'''unset NODE_OPTIONS && "{PCLI}" eval "(function(){{var t=document.body.innerText;var i=t.indexOf('作者声明');if(i<0)i=t.indexOf('发布时间');if(i<0)return'NO_DESC';var s=t.substring(i);return s.split('\\\\n').filter(function(l){{return l.trim().length>15&&!/发布时间|粉丝\\\\d|获赞\\\\d|登录|合集|^第\\\\d+集|^\\\\d+:/.test(l.trim());}}).slice(0,8).join('@@@');}})()"''', timeout=10)
    
    bash(f'unset NODE_OPTIONS && "{PCLI}" close', timeout=10)
    
    # 解析输出
    for line in out.split('\n'):
        line = line.strip()
        if line.startswith('"') and '@@@' in line:
            text = line.strip('"').replace('@@@', '\n').replace('\\n', '\n')
            if text and text != 'NO_DESC' and len(text) > 20:
                return text
        if '@@@' in line and not line.startswith('###'):
            text = line.replace('@@@', '\n').replace('\\n', '\n')
            if len(text) > 20:
                return text
    
    return None


def main():
    import sys
    do_update = '--update' in sys.argv
    
    # 清理
    try: bash(f'unset NODE_OPTIONS && "{PCLI}" kill-all', timeout=10)
    except: pass
    
    with open("data.json", "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    bloggers = [a for a in d["articles"] if a.get("source") == "blogger"]
    print(f"共 {len(bloggers)} 条视频\n")
    
    results = {}
    for i, v in enumerate(bloggers):
        url = v.get("url", "")
        name = v.get("blogger_name", "")
        vid = str(v.get("id", ""))
        
        print(f"[{i+1}/{len(bloggers)}] {name}", end=" ")
        
        if "douyin.com" not in url:
            if "bilibili.com" in url:
                print("(B站)")
            else:
                print("(无URL)")
            continue
        
        try:
            desc = extract_desc(url)
            if desc:
                results[vid] = desc
                print(f"✅ {len(desc)}字")
            else:
                print("⚠️ 无描述")
        except Exception as e:
            print(f"❌ {e}")
            try: bash(f'unset NODE_OPTIONS && "{PCLI}" close', timeout=10)
            except: pass
    
    try: bash(f'unset NODE_OPTIONS && "{PCLI}" kill-all', timeout=10)
    except: pass
    
    # 更新数据
    updated = 0
    for a in d["articles"]:
        if a.get("source") == "blogger":
            vid = str(a.get("id", ""))
            if vid in results and results[vid] != a.get("content_intro", ""):
                a["content_intro"] = results[vid]
                updated += 1
    
    if updated > 0:
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        
        if do_update:
            import gen_js_data
            gen_js_data.main()
            print(f"\n✅ {updated} 条文案已更新 → data.json + data.js 已刷新")
        else:
            print(f"\n✅ {updated} 条文案已更新 → data.json")
        
        # 显示更新内容
        print("\n--- 更新预览 ---")
        for a in d["articles"]:
            if a.get("source") == "blogger":
                vid = str(a.get("id", ""))
                if vid in results:
                    print(f"\n[{a['blogger_name']}] {a.get('date','?')}")
                    print(f"  {a['content_intro'][:120]}...")
    else:
        print(f"\n无更新")
    
    return updated


if __name__ == "__main__":
    main()
