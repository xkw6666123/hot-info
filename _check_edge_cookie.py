"""检查 Edge 抖音 cookie（需要管理员权限）"""
import browser_cookie3

try:
    cj = browser_cookie3.edge(domain_name='douyin.com')
    cookie_str = '; '.join(f'{c.name}={c.value}' for c in cj if 'douyin' in c.domain)
    
    print(f'Edge Cookie 总长度: {len(cookie_str)}')
    
    key_cookies = ['sessionid', 'msToken', 'ttwid', 'odin_tt', 'passport_csrf_token']
    for name in key_cookies:
        found = any(c.name == name for c in cj)
        status = 'Y' if found else 'N'
        print(f'  {name}: {status}')
        
        if name == 'sessionid' and found:
            for c in cj:
                if c.name == 'sessionid':
                    print(f'  sessionid_val: {c.value[:40]}...')
                    break
    
    # 输出完整 cookie 到文件供后续使用
    with open('_edge_cookie.txt', 'w', encoding='utf-8') as f:
        f.write(cookie_str)
    print(f'\nCookie 已保存到 _edge_cookie.txt')
    
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
