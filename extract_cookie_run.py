# -*- coding: utf-8 -*-
"""从 Chrome 提取抖音登录 Cookie 并保存。
关键：Chrome 127+ 的 cookie 解密后明文前有 32 字节填充前缀，必须剥离。
"""
import sys, os, json, sqlite3, shutil, base64, tempfile
sys.stdout.reconfigure(encoding='utf-8')
from win32crypt import CryptUnprotectData
from Cryptodome.Cipher import AES


def extract_douyin_cookie():
    st = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data\Local State')
    db = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data\Default\Network\Cookies')
    if not (os.path.exists(st) and os.path.exists(db)):
        return None, "Chrome cookie 库不存在"

    ls = json.load(open(st, 'r', encoding='utf-8'))
    ek = base64.b64decode(ls['os_crypt']['encrypted_key'])[5:]
    key = CryptUnprotectData(ek, None, None, None, 0)[1]

    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    shutil.copy2(db, tmp.name)
    conn = sqlite3.connect(f'file:{tmp.name}?mode=ro', uri=True)
    conn.text_factory = bytes
    cur = conn.cursor()
    cur.execute('SELECT name, encrypted_value FROM cookies WHERE host_key LIKE ?', ('%douyin.com%',))
    rows = cur.fetchall()
    conn.close()
    os.unlink(tmp.name)

    cookies = {}
    for name, enc in rows:
        n = name.decode('utf-8', 'replace')
        if enc[:3] not in (b'v10', b'v20'):
            continue
        try:
            nonce = enc[3:15]
            ct = enc[15:]
            c = AES.new(key, AES.MODE_GCM, nonce=nonce)
            raw = c.decrypt_and_verify(ct[:-16], ct[-16:])
            val = raw[32:].decode('utf-8', 'replace')  # 剥离 32 字节前缀
            if val:
                cookies[n] = val
        except Exception:
            pass
    return cookies, None


if __name__ == '__main__':
    cookies, err = extract_douyin_cookie()
    if err or not cookies:
        print(f'❌ 提取失败: {err}')
        sys.exit(1)
    has_session = 'sessionid' in cookies
    print(f'✅ 提取 {len(cookies)} 个 cookie | 登录态: {"已登录" if has_session else "未登录"}')
    cookie_str = '; '.join(f'{k}={v}' for k, v in cookies.items())
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'douyin_cookies.txt')
    open(out, 'w', encoding='utf-8').write(cookie_str)
    print(f'📁 已保存 {len(cookie_str)} 字符到 douyin_cookies.txt')
