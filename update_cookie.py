#!/usr/bin/env python3
"""一键更新抖音 Cookie 到 douyin-api 配置文件

使用方法:
  1. 浏览器打开 https://www.douyin.com/ 并登录
  2. F12 → Console（控制台），粘贴：
     document.cookie
     回车，复制输出的完整结果
  3. 运行: python update_cookie.py
     粘贴刚才复制的 Cookie 字符串，回车即可
"""

import sys
import os
import yaml

# 确定 config.yaml 路径
DOUYIN_CONFIG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "douyin-api", "crawlers", "douyin", "web", "config.yaml"
)
DOUYIN_CONFIG = os.path.normpath(DOUYIN_CONFIG)

def main():
    if not os.path.exists(DOUYIN_CONFIG):
        print(f"❌ 找不到配置文件: {DOUYIN_CONFIG}")
        sys.exit(1)

    print("=" * 60)
    print("🔄 抖音 Cookie 更新工具")
    print("=" * 60)
    print()
    print("📋 获取 Cookie 方法 (任选一种):")
    print()
    print("  方法1️⃣  浏览器控制台 (最简单):")
    print("    1. 打开 https://www.douyin.com/ 并登录")
    print("    2. 按 F12 打开开发者工具")
    print("    3. 点击 Console (控制台) 标签")
    print('    4. 输入: document.cookie')
    print("    5. 复制输出的完整字符串")
    print()
    print("  方法2️⃣  Network 标签 (最完整，包含 httpOnly):")
    print("    1. 打开 https://www.douyin.com/ 并登录")
    print("    2. 按 F12 → Network (网络) 标签")
    print("    3. 刷新页面 (F5)")
    print("    4. 点击任意一个 douyin.com 的请求")
    print("    5. 右侧 Headers → Request Headers → Cookie")
    print("    6. 复制完整的 Cookie 值")
    print()
    print("=" * 60)

    cookie = input("请粘贴 Cookie 字符串，然后按回车:\n> ").strip()

    if not cookie or len(cookie) < 50:
        print("❌ Cookie 太短或为空，请重新运行并粘贴完整的 Cookie")
        sys.exit(1)

    # 读取现有配置
    with open(DOUYIN_CONFIG, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 更新 Cookie
    old_cookie = config["TokenManager"]["douyin"]["headers"]["Cookie"]
    config["TokenManager"]["douyin"]["headers"]["Cookie"] = cookie

    # 写回
    with open(DOUYIN_CONFIG, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)

    print()
    print("✅ Cookie 已更新!")
    print(f"📁 配置文件: {DOUYIN_CONFIG}")
    print()

    # 验证关键字段
    cookie_lower = cookie.lower()
    key_fields = {
        "sessionid": "登录会话 (核心)",
        "sessionid_ss": "登录会话辅助",
        "passport_csrf_token": "防CSRF令牌",
        "sid_guard": "用户身份保护",
        "ttwid": "设备/会话标识",
        "odin_tt": "用户追踪ID",
    }
    print("🔍 Cookie 包含的关键字段:")
    for key, desc in key_fields.items():
        found = "✅" if key in cookie_lower else "❌"
        print(f"  {found} {key} - {desc}")

    if "sessionid" not in cookie_lower:
        print()
        print("⚠️  警告: Cookie 中缺少 sessionid，可能未登录!")
        print("   请确保在已登录状态下获取 Cookie")
    else:
        print()
        print("🎉 Cookie 包含登录凭证，配置完成!")

    print()
    print("💡 提示: Cookie 有效期通常为1-3个月，过期后需要重新更新")


if __name__ == "__main__":
    main()
