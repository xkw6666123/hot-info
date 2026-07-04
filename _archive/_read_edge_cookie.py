"""读取 Edge 抖音 cookie（直接读 SQLite + DPAPI 解密）"""
import sqlite3, os, shutil, sys

db_path = r'C:\Users\Kevin\AppData\Local\Microsoft\Edge\User Data\Default\Network\Cookies'
print(f'DB exists: {os.path.exists(db_path)}, size: {os.path.getsize(db_path)}')

# 复制一份再读
tmp = db_path + '.tmp'
shutil.copy2(db_path, tmp)

conn = sqlite3.connect(tmp)
cur = conn.cursor()

rows = cur.execute("SELECT name, encrypted_value, host_key FROM cookies WHERE host_key LIKE '%douyin%'").fetchall()
print(f'\nFound {len(rows)} douyin cookies:')

key_cookies = ['sessionid', 'msToken', 'ttwid', 'odin_tt', 'passport_csrf_token']
for name, enc_val, host in rows:
    is_dpapi = isinstance(enc_val, bytes) and len(enc_val) > 0 and enc_val[0:1] == b'\x01'
    marker = ' [ENCRYPTED]' if is_dpapi else (' [PLAIN]' if isinstance(enc_val, bytes) and len(enc_val) > 0 else ' [EMPTY]')
    print(f'  {name}: host={host} len={len(enc_val) if enc_val else 0}{marker}')

# 尝试 DPAPI 解密
print('\n--- DPAPI Decrypt Test ---')
try:
    import ctypes
    import ctypes.wlltypes
    
    def dpapi_decrypt(encrypted):
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [('cbData', ctypes.c_ulong), ('pbData', ctypes.POINTER(ctypes.c_char))]
        
        blob_in = DATA_BLOB(len(encrypted), ctypes.create_string_buffer(encrypted, len(encrypted)))
        blob_out = DATA_BLOB()
        
        if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            decrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            return decrypted.decode('utf-8', errors='replace')
        return None
    
    for name, enc_val, host in rows:
        if name in key_cookies or name == 'sessionid':
            if isinstance(enc_val, bytes) and len(enc_val) > 0 and enc_val[0:1] == b'\x01':
                dec = dpapi_decrypt(enc_val)
                print(f'  {name}: DECRYPTED={dec[:50] if dec else "FAIL"}...')
except Exception as e:
    print(f'DPAPI Error: {e}')
    import traceback
    traceback.print_exc()

conn.close()
os.remove(tmp)
