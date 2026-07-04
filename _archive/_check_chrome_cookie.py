"""检查 Chrome 抖音 cookie（管理员权限）"""
import browser_cookie3, json

try:
    cj = browser_cookie3.chrome(domain_name='douyin.com')
    cookie_str = '; '.join(f'{c.name}={c.value}' for c in cj if 'douyin' in c.domain')

    result = {
        'cookie_len': len(cookie_str),
        'cookies': {}
    }
    
    for c in cj:
        name = c.name
        result['cookies'][name] = {
            'has_value': bool(c.value),
            'value_preview': c.value[:50] if c.value else '',
        }
    
    # 输出结果
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 同时保存 cookie 供后续使用
    with open('_chrome_cookie.txt', 'w', encoding='utf-8') as f:
        f.write(cookie_str)
    print('\nSAVED_TO: _chrome_cookie.txt')

except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
