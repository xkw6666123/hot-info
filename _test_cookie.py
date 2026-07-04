# -*- coding: utf-8 -*-
"""Check all douyin cookies and test with full cookie extraction"""
import browser_cookie3

print("=== All cookies for douyin.com ===")
cj = browser_cookie3.chrome(domain_name='douyin.com')
for c in cj:
    name_len = len(c.name)
    val_preview = str(c.value)[:30] + '...' if len(str(c.value)) > 30 else str(c.value)
    domain = c.domain
    print("  {}={} [domain={}]".format(c.name, val_preview, c.domain))

print("\nTotal cookies: {}".format(len(cj)))

# Also try reading from Chrome's cookie DB directly via SQLite
import os, sqlite3, tempfile

chrome_paths = [
    os.path.expanduser("~/AppData/Local/Google/Chrome/User Data/Default/Cookies"),
    os.path.expanduser("~/AppData/Local/Google/Chrome/User Data/Profile */Cookies"),
]

import glob
cookie_dbs = []
for pattern in chrome_paths:
    cookie_dbs.extend(glob.glob(pattern))

print("\n=== Chrome Cookie DBs found ===")
for db in cookie_dbs:
    print("  {}".format(db))

# Try to find sessionid in the raw DB
if cookie_dbs:
    db_path = cookie_dbs[0]
    # Copy DB first (Chrome locks it)
    import shutil
    temp_db = os.path.join(tempfile.gettempdir(), 'chrome_cookies_temp.db')
    try:
        shutil.copy2(db_path, temp_db)
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Search for douyin sessionid
        cursor.execute("""
            SELECT host_key, name, length(value), encrypted_value 
            FROM cookies 
            WHERE host_key LIKE '%douyin%' 
            AND (name='sessionid' OR name='sid_guard' OR name='sid_tt' OR name='passport_csrf_token')
            ORDER BY host_key
        """)
        rows = cursor.fetchall()
        if rows:
            print("\n=== Critical cookies in DB ===")
            for r in rows:
                print("  host={} name={} val_len={}".format(r[0], r[1], r[2]))
        else:
            print("\nNo sessionid/sid cookies found for douyin in DB")
            
        # Count all douyin cookies
        cursor.execute("SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%douyin%'")
        total = cursor.fetchone()[0]
        print("Total douyin cookies in DB: {}".format(total))
        
        conn.close()
        os.unlink(temp_db)
    except Exception as e:
        print("DB access error: {}".format(e))
