# -*- coding: utf-8 -*-
"""管理员权限下读取浏览器cookie（诊断用）"""
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
print(f"=== Cookie 诊断 (PID={os.getpid()}) ===")

# 尝试 browser_cookie3
try:
    import browser_cookie3
    for bname, bfunc in [("Chrome", lambda: browser_cookie3.chrome(domain_name='douyin.com')),
                          ("Edge", lambda: browser_cookie3.edge(domain_name='douyin.com'))]:
        try:
            cj = bfunc()
            cookies = list(cj)
            print(f"\n--- {bname} 抖音 cookie ({len(cookies)}个) ---")
            has_sessionid = False
            has_msToken = False
            for c in cookies:
                if c.name == 'sessionid':
                    has_sessionid = True
                    print(f"  ✅ sessionid = {c.value[:20]}... (长度:{len(c.value)})")
                elif c.name == 'msToken':
                    has_msToken = True
                    print(f"  ✅ msToken = {c.value[:20]}... (长度:{len(c.value)})")
                elif c.name in ('ttwid', 'odin_tt', 'passport_csrf_token'):
                    print(f"  ℹ️  {c.name} = {str(c.value)[:30]}...")
            if not has_sessionid:
                print(f"  ❌ 缺少 sessionid（未登录）")
            if not has_msToken:
                print(f"  ⚠️  缺少 msToken")
            
            # 输出完整cookie字符串
            cookie_str = '; '.join(f'{c.name}={c.value}' for c in cookies if 'douyin' in str(c.domain))
            print(f"\n  完整cookie长度: {len(cookie_str)}")
            # 只打印前200字符避免日志膨胀
            print(f"  前200字符: {cookie_str[:200]}")
            
            if has_sessionid:
                # 写到文件供后续使用
                with open('_valid_cookie.txt', 'w', encoding='utf-8') as f:
                    f.write(cookie_str)
                print(f"\n  ✅ 已保存到 _valid_cookie.txt")
                
        except Exception as e:
            print(f"\n--- {bname} 失败: {type(e).__name__}: {e}")
except ImportError:
    print("❌ 需要安装: pip install browser_cookie3")

print("\n=== 完成 ===")
