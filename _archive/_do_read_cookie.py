# -*- coding: utf-8 -*-
import os, sys, traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))
log_path = '_cookie_diag.log'

with open(log_path, 'a', encoding='utf-8') as log:
    def w(msg):
        s = str(msg)
        log.write(s + '\n')
        log.flush()
        print(s)

    w('=== Python Cookie诊断开始 ===')

    try:
        import browser_cookie3
        for bname, bfunc in [
            ('Chrome', lambda: browser_cookie3.chrome(domain_name='douyin.com')),
            ('Edge', lambda: browser_cookie3.edge(domain_name='douyin.com'))
        ]:
            try:
                w(f'--- {bname} ---')
                cj = bfunc()
                cookies = list(cj)
                w(f'Cookie数: {len(cookies)}')
                
                has_sid = False
                has_mst = False
                for c in cookies:
                    d = str(c.domain)
                    if 'sessionid' == c.name:
                        has_sid = True
                        w(f'  OK sessionid len={len(c.value)} val={c.value[:25]}...')
                    elif 'msToken' == c.name:
                        has_mst = True
                        w(f'  OK msToken len={len(c.value)} val={c.value[:25]}...')
                    elif c.name in ('ttwid', 'odin_tt', 'passport_csrf_token'):
                        w(f'  info {c.name}={str(c.value)[:35]}...')
                
                if not has_sid:
                    w('  FAIL no sessionid')
                if not has_mst:
                    w('  WARN no msToken')

                cookie_str = '; '.join(
                    '{}={}'.format(c.name, c.value)
                    for c in cookies if 'douyin' in str(c.domain)
                )
                w(f'total cookie str len={len(cookie_str)}')

                if has_sid and len(cookie_str) > 100:
                    with open('_valid_cookie.txt', 'w', encoding='utf-8') as f:
                        f.write(cookie_str)
                    w('SAVED _valid_cookie.txt')

            except Exception as e:
                w('{} ERR: {}: {}'.format(bname, type(e).__name__, e))
    except ImportError as e:
        w('ImportError: {}'.format(e))

    w('=== Python诊断结束 ===')
