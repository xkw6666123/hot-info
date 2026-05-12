#!/usr/bin/env python3
"""
免费抖音下载方案：获取登录 cookies
1. 运行此脚本 → 打开浏览器
2. 手动扫码登录抖音
3. cookies 自动保存到 douyin_cookies.txt
4. 之后 yt-dlp --cookies douyin_cookies.txt 免费下载
"""
import subprocess, os, time, json

WORK = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(WORK, "douyin_cookies.txt")

print("=" * 50)
print("  打开浏览器 → 请在 60 秒内扫码登录抖音")
print("=" * 50)

# 打开抖音首页
subprocess.run([
    "playwright-cli", "open", "https://www.douyin.com/"
], env={**os.environ, "NODE_OPTIONS": ""})

time.sleep(3)

# 等用户登录
for i in range(60, 0, -5):
    print(f"\r等待登录... {i}秒 ", end="", flush=True)
    time.sleep(5)
print()

# 保存 cookies
print("保存 cookies...")
result = subprocess.run([
    "playwright-cli", "state-save", COOKIE_FILE.replace(".txt", ".json")
], capture_output=True, text=True, env={**os.environ, "NODE_OPTIONS": ""})

# 转换为 Netscape 格式给 yt-dlp
import json as j
try:
    with open(COOKIE_FILE.replace(".txt", ".json")) as f:
        state = j.load(f)
    cookies = state.get("cookies", [])
    
    with open(COOKIE_FILE, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            domain = c.get("domain", "")
            if "douyin" in domain or "iesdouyin" in domain:
                f.write(f"{domain}\tTRUE\t{c.get('path','/')}\t"
                       f"{'TRUE' if c.get('secure') else 'FALSE'}\t"
                       f"{int(c.get('expires',-1))}\t"
                       f"{c.get('name','')}\t{c.get('value','')}\n")
    
    print(f"✅ Cookies 已保存到: {COOKIE_FILE}")
    print(f"   共 {len([c for c in cookies if 'douyin' in c.get('domain','')])} 个抖音 cookies")
    
    print("\n现在可以用 yt-dlp 免费下载：")
    print(f"  yt-dlp --cookies {COOKIE_FILE} <抖音链接>")
    
except Exception as e:
    print(f"❌ 保存失败: {e}")

subprocess.run(["playwright-cli", "close"], env={**os.environ, "NODE_OPTIONS": ""})
