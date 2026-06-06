#!/usr/bin/env python3
"""从 Chrome 浏览器提取抖音 Cookie 并更新到配置文件

原理：读取 Chrome 加密的 Cookies 数据库，用 Windows DPAPI 解密，
筛选 douyin.com 的 Cookie，拼接成可用的 Cookie 字符串。
"""

import os
import sys
import json
import sqlite3
import shutil
import base64
import tempfile
from pathlib import Path

# 需要关闭 Chrome 才能读取数据库？不，我们复制一份
CHROME_COOKIE_DB = os.path.expandvars(
    r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Network\Cookies"
)
CHROME_LOCAL_STATE = os.path.expandvars(
    r"%LOCALAPPDATA%\Google\Chrome\User Data\Local State"
)
EDGE_COOKIE_DB = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Network\Cookies"
)
EDGE_LOCAL_STATE = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Local State"
)


def get_encryption_key(local_state_path: str) -> bytes:
    """从 Chrome/Edge 的 Local State 文件中获取解密密钥"""
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)

    encrypted_key = base64.b64decode(
        local_state["os_crypt"]["encrypted_key"]
    )
    # 去掉 'DPAPI' 前缀 (5 bytes)
    encrypted_key = encrypted_key[5:]

    # 用 Windows DPAPI 解密
    from win32crypt import CryptUnprotectData

    return CryptUnprotectData(encrypted_key, None, None, None, 0)[1]


def decrypt_cookie_value(encrypted_value: bytes, key: bytes) -> str:
    """解密 Cookie 值 (Chrome v80+ 使用 AES-256-GCM)"""
    from Cryptodome.Cipher import AES

    # v10/v20 格式: 前3字节是版本标记 "v10" 或 "v20"
    if encrypted_value[:3] == b"v10" or encrypted_value[:3] == b"v20":
        # AES-256-GCM: nonce(12) + ciphertext + tag(16)
        nonce = encrypted_value[3:15]
        ciphertext_with_tag = encrypted_value[15:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(
            ciphertext_with_tag[:-16], ciphertext_with_tag[-16:]
        )
        return plaintext.decode("utf-8", errors="replace")
    else:
        # 旧格式或明文
        return encrypted_value.decode("utf-8", errors="replace")


def extract_cookies(db_path: str, key: bytes, domain: str) -> dict:
    """从 Cookies 数据库提取指定域名的 Cookie"""
    # 复制数据库文件 (Chrome 可能正在使用)
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    shutil.copy2(db_path, tmp.name)

    try:
        conn = sqlite3.connect(f"file:{tmp.name}?mode=ro", uri=True)
        conn.text_factory = bytes
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name, encrypted_value, host_key FROM cookies WHERE host_key LIKE ?",
            (f"%{domain}%",),
        )
        rows = cursor.fetchall()
        conn.close()

        cookies = {}
        for name, enc_val, host in rows:
            try:
                name_str = name.decode("utf-8", errors="replace")
                value = decrypt_cookie_value(enc_val, key)
                cookies[name_str] = value
            except Exception as e:
                print(f"  ⚠️ 跳过 {name.decode('utf-8','replace')}: {e}")

        return cookies
    finally:
        os.unlink(tmp.name)


def format_cookie_header(cookies: dict) -> str:
    """将 Cookie 字典拼成 HTTP Cookie Header 格式"""
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def main():
    print("=" * 60)
    print("🔍 从浏览器提取抖音 Cookie")
    print("=" * 60)

    # 尝试 Chrome 和 Edge
    sources = [
        ("Chrome", CHROME_COOKIE_DB, CHROME_LOCAL_STATE),
        ("Edge", EDGE_COOKIE_DB, EDGE_LOCAL_STATE),
    ]

    cookies = {}
    source_name = ""

    for name, db_path, state_path in sources:
        if not os.path.exists(db_path):
            print(f"  ❌ {name} Cookies 数据库不存在")
            continue
        if not os.path.exists(state_path):
            print(f"  ❌ {name} Local State 不存在")
            continue

        print(f"\n📂 正在从 {name} 提取...")
        try:
            key = get_encryption_key(state_path)
            cookies = extract_cookies(db_path, key, "douyin.com")
            source_name = name
            break
        except Exception as e:
            print(f"  ❌ {name} 提取失败: {e}")
            # 尝试后备
            pass

    if not cookies:
        print("\n" + "=" * 60)
        print("❌ 无法从浏览器自动提取 Cookie")
        print()
        print("📋 请手动获取 (任选其一):")
        print()
        print("  方法1️ 浏览器控制台:")
        print("    1. 打开 https://www.douyin.com/ 确保已登录")
        print("    2. 按 F12 → Console (控制台)")
        print('    3. 输入: document.cookie')
        print("    4. 复制输出结果")
        print()
        print("  方法2️ Network标签 (推荐):")
        print("    1. 打开 https://www.douyin.com/ 确保已登录")
        print("    2. 按 F12 → Network (网络)")
        print("    3. 刷新页面 (F5)")
        print("    4. 点击任意 douyin.com 请求")
        print("    5. Headers → Request Headers → Cookie")
        print("    6. 复制完整 Cookie 值")
        print()
        print('  然后运行: python update_cookie.py 粘贴Cookie')
        print("=" * 60)
        sys.exit(1)

    print(f"\n✅ 成功从 {source_name} 提取 {len(cookies)} 个 Cookie")
    print()

    # 显示关键 Cookie
    key_fields = [
        "sessionid", "sessionid_ss", "sid_guard", "sid_tt",
        "uid_tt", "uid_tt_ss", "ttwid", "passport_csrf_token",
        "odin_tt", "msToken", "s_v_web_id"
    ]
    print("🔑 关键 Cookie 字段:")
    for kf in key_fields:
        if kf in cookies:
            val = cookies[kf]
            display = val[:30] + "..." if len(val) > 30 else val
            print(f"  ✅ {kf} = {display}")
        else:
            print(f"  ❌ {kf} = 缺失")

    has_session = any("sessionid" in k for k in cookies)
    if not has_session:
        print("\n⚠️  警告: 缺少 sessionid，可能未登录或Cookie不完整")
        print("   请手动登录 douyin.com 后再试")

    # 拼接完整 Cookie 字符串
    cookie_str = format_cookie_header(cookies)
    print(f"\n📝 Cookie 总长度: {len(cookie_str)} 字符")

    # 更新配置文件
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.normpath(
        os.path.join(script_dir, "..", "douyin-api", "crawlers", "douyin", "web", "config.yaml")
    )

    import yaml

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    old_len = len(config["TokenManager"]["douyin"]["headers"]["Cookie"])
    config["TokenManager"]["douyin"]["headers"]["Cookie"] = cookie_str

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)

    print(f"📁 已更新: {config_path}")
    print(f"   旧 Cookie: {old_len} 字符 → 新 Cookie: {len(cookie_str)} 字符")
    print()
    print("🎉 完成! 现在可以运行 free_douyin.py 测试")

    # 同时保存到 douyin_cookies.txt (Netscape 格式备用)
    cookie_txt = os.path.join(script_dir, "douyin_cookies.txt")
    with open(cookie_txt, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write("# Auto-generated from Chrome\n\n")
        for name, value in cookies.items():
            f.write(f".douyin.com\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")
    print(f"📁 Netscape 格式已保存: {cookie_txt}")


if __name__ == "__main__":
    main()
