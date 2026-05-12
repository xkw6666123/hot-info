#!/usr/bin/env python3
"""
一键免费 ASR（需在 Edge 未运行时执行）
用法：重启电脑后立即运行 python tools/free_douyin_once.py
"""
import subprocess, os, sqlite3, json, sys, shutil

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFMPEG = "C:/Users/Kevin/ffmpeg/ffmpeg-master-latest-win64-gpl-shared/bin/ffmpeg.exe"
PY = sys.executable

def extract_cookies():
    """从 Edge 数据库提取抖音 cookies（Edge 必须未运行）"""
    src = os.path.expanduser("~/AppData/Local/Microsoft/Edge/User Data/Default/Network/Cookies")
    dst = os.path.join(WORK, "edge_cookies.db")
    
    try:
        shutil.copy2(src, dst)
    except PermissionError:
        print("❌ Edge 正在运行！请关闭所有 Edge 窗口和 WebView 应用后重试")
        return None
    
    conn = sqlite3.connect(dst)
    rows = conn.execute(
        "SELECT host_key,name,value,path,expires_utc,is_secure FROM cookies WHERE host_key LIKE '%douyin%'"
    ).fetchall()
    conn.close()
    os.remove(dst)
    
    if not rows:
        print("❌ 未找到抖音 cookies，请先在 Edge 中登录 douyin.com")
        return None
    
    cookie_file = os.path.join(WORK, "douyin_cookies.txt")
    with open(cookie_file, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for r in rows:
            secure = "TRUE" if r[5] else "FALSE"
            f.write(f"{r[0]}\tTRUE\t{r[3]}\t{secure}\t{r[4]}\t{r[1]}\t{r[2]}\n")
    
    print(f"✅ 已提取 {len(rows)} 个抖音 cookies")
    return cookie_file

# 直接运行
if __name__ == "__main__":
    print("=" * 50)
    print("  免费抖音 ASR - 一键运行")
    print("=" * 50)
    
    ck = extract_cookies()
    if ck:
        print(f"\nCookies 文件: {ck}")
        print("\n现在可以运行：")
        print(f"  python asr_extract.py --free")
    else:
        print("\n请先在 Edge 登录 douyin.com，然后重启电脑再运行此脚本")
